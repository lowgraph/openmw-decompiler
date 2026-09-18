"""Decode profile-resolved foundation records into app-facing JSON catalogs."""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time

from extract_foundation import ROOT, fields, load_config
from export_items import (ATTRIBUTES, SKILLS, CATEGORIES, ExportError, Formatter,
                          Plugin, Record, choice, decode, unpack)
from effect_names import EFFECT_GMSTS

VERSION = '1.1.0'
BOOK_TEXT = 'BookText'
EXTRA = {'GMST':'GameSettings', 'MGEF':'MagicEffects', 'ENCH':'Enchantments',
         'SPEL':'Spells', 'RACE':'Races', 'CLAS':'Classes', 'BSGN':'Birthsigns', 'SKIL':'Skills'}
CATALOGS = CATEGORIES | EXTRA
SPECIALIZATIONS = ['combat', 'magic', 'stealth']
SCHOOLS = ['alteration','conjuration','destruction','illusion','mysticism','restoration']
SQL = '''SELECT v.id,v.payload,o.name,p.name FROM resolved_records r
 JOIN record_versions v ON v.id=r.winner_id JOIN plugins o ON o.id=r.origin_plugin_id
 JOIN plugins p ON p.id=v.plugin_id
 WHERE r.profile_id=? AND r.record_type=? AND r.record_key=? AND v.deleted=0'''


class Store(Mapping):
    """Lazy source records: only the requested catalog is walked, no world BLOBs."""
    def __init__(self, db, profile):
        self.db, self.profile = db, profile

    def __getitem__(self, key):
        row = self.db.execute(SQL, (self.profile,*key)).fetchone()
        if row is None:
            raise KeyError(key)
        version, payload, origin, winner = row
        world = 'vanilla' if origin.casefold() in ('morrowind.esm','tribunal.esm','bloodmoon.esm') else 'tamriel_rebuilt'
        return Record(key[0], [(tag,bytes(value)) for tag,value,_,_ in fields(payload)],
                      Plugin(Path(winner), world), world)

    def __iter__(self):
        for tag,key in self.db.execute('SELECT record_type,record_key FROM live_records WHERE profile_id=?',(self.profile,)):
            yield tag,key

    def __len__(self):
        return self.db.execute('SELECT count(*) FROM live_records WHERE profile_id=?',(self.profile,)).fetchone()[0]

    def keys_for(self, tag):
        for key, in self.db.execute('SELECT record_key FROM live_records WHERE profile_id=? AND record_type=? ORDER BY record_key',(self.profile,tag)):
            yield key


class CatalogDecoder(Formatter):
    def __init__(self, store, versions, encoding):
        # Avoid Formatter's scan of all record types. Only GMST names are needed.
        self.winners, self.versions, self.encoding = store, versions, encoding
        self.gmsts = {}
        self.enchantments = {}
        self.links = set()
        for key in store.keys_for('GMST'):
            data = dict(store['GMST',key].fields)
            if 'STRV' in data:
                self.gmsts[key] = decode(data['STRV'],encoding)

    def enchantment(self, ident):
        # Item rows reference the separate enchantment catalog, not duplicated effects.
        if not ident:
            return None
        self.links.add(('ENCH',ident.casefold()))
        return ident.casefold()

    def effect_base(self, ident, skill, attribute):
        row = super().effect_base(ident,skill,attribute)
        self.links.add(('MGEF',str(ident)))
        row['effectKey'] = str(ident)
        return row

    def parse(self, tag, key):
        record = self.winners[tag,key]
        data = dict(record.fields)
        text = lambda name: decode(data.get(name),self.encoding)
        if tag in CATEGORIES:
            row = self.item(record)
            if row is None:
                return None
            if 'enchantment' in row:
                row['enchantmentId'] = row.pop('enchantment')
            return row
        row = {'id': text('NAME') or key, 'name': text('FNAM')}
        powers = [decode(v,self.encoding).casefold() for k,v in record.fields if k == 'NPCS']
        if tag == 'GMST':
            kinds = [k for k in ('STRV','INTV','FLTV') if k in data]
            if len(kinds) > 1:
                raise ExportError('GMST has multiple value types')
            kind = kinds[0] if kinds else None
            row.update(valueType={'STRV':'string','INTV':'integer','FLTV':'float',None:'unset'}[kind],
                       value=text(kind) if kind == 'STRV' else unpack('i' if kind == 'INTV' else 'f',data[kind])[0] if kind else None)
        elif tag == 'ENCH':
            kind,cost,charge,flags = unpack('4i',data['ENDT'])
            row.update(castType=choice(['cast_once','when_strikes','when_used','constant_effect'],kind,'cast type'),
                cost=cost,charges=charge,autoCalculate=bool(flags&1),flagsRaw=flags,
                effects=[self.effect(v) for k,v in record.fields if k=='ENAM'])
        elif tag == 'SPEL':
            kind,cost,flags = unpack('3i',data['SPDT'])
            row.update(type=choice(['spell','ability','blight_disease','common_disease','curse','power'],kind,'spell type'),
                cost=cost,flagsRaw=flags,autoCalculate=bool(flags&1),playerStart=bool(flags&2),alwaysSucceeds=bool(flags&4),
                effects=[self.effect(v) for k,v in record.fields if k=='ENAM'])
        elif tag == 'RACE':
            values = unpack('30i4fI',data['RADT'])
            row.update(description=text('DESC'),skillBonuses=[
                {'skill':choice(SKILLS,values[i],'race skill'),'bonus':values[i+1]} for i in range(0,14,2) if values[i]!=-1],
                attributes={attr:{'male':values[14+i*2],'female':values[15+i*2]} for i,attr in enumerate(ATTRIBUTES)},
                height={'male':values[30],'female':values[31]},weight={'male':values[32],'female':values[33]},
                flagsRaw=values[34],playable=bool(values[34]&1),beast=bool(values[34]&2),spellIds=powers)
        elif tag == 'CLAS':
            values = unpack('13iB3xI',data['CLDT'])
            row.update(description=text('DESC'),favoredAttributes=[choice(ATTRIBUTES,i,'class attribute') for i in values[:2]],
                specialization=choice(SPECIALIZATIONS,values[2],'specialization'),
                minorSkills=[choice(SKILLS,values[i],'minor skill') for i in range(3,13,2)],
                majorSkills=[choice(SKILLS,values[i],'major skill') for i in range(4,13,2)],
                playable=bool(values[13]),servicesRaw=values[14])
        elif tag == 'BSGN':
            row.update(description=text('DESC'),texture=text('TNAM') or None,spellIds=powers)
        elif tag == 'SKIL':
            attr,spec,*uses = unpack('ii4f',data['SKDT'])
            skill = choice(SKILLS,int(key),'skill')
            gmst = 'sskill'+skill.replace('_','')
            row.update(skill=skill,name=self.gmsts.get(gmst,skill.replace('_',' ').title()),
                governingAttribute=choice(ATTRIBUTES,attr,'governing attribute'),
                specialization=choice(SPECIALIZATIONS,spec,'specialization'),useValues=uses,description=text('DESC'))
        elif tag == 'MGEF':
            school,cost,flags,r,g,b,size,speed,cap = unpack('ifIiii3f',data['MEDT'])
            gmst = choice(EFFECT_GMSTS,int(key),'effect')
            row.update(name=self.gmsts.get(gmst,gmst),effectId=int(key),school=choice(SCHOOLS,school,'school'),
                baseCost=cost,flagsRaw=flags,allowSpellmaking=bool(flags&0x200),allowEnchanting=bool(flags&0x400),
                description=text('DESC'),color={'r':r,'g':g,'b':b},size=size,speed=speed,sizeCap=cap,
                assets={k:text(k) or None for k in ('ITEX','PTEX','CVFX','BVFX','HVFX','AVFX','CSND','BSND','HSND','ASND')})
        for ident in powers:
            self.links.add(('SPEL',ident))
        return row


def write_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def build(database, output, profiles=None):
    if not database.is_file():
        raise ExportError(f'Foundation not found: {database}')
    output = output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    lock = output/'build.lock'
    try:
        fd = os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:
        raise ExportError(f'Build lock exists: {lock}; check for another build before removing a stale lock') from exc
    os.close(fd)
    try:
        with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('PRAGMA cache_size=-16384')
            db.execute('BEGIN')
            meta = {k:json.loads(v) for k,v in db.execute('SELECT key,value FROM metadata')}
            if meta.get('schemaVersion') != 1:
                raise ExportError('Unsupported foundation schema version')
            available = {p[0]:{'id':p[0],'world':p[1],'version':p[2],'arce':bool(p[3])} for p in db.execute('SELECT id,world,version,arce FROM profiles')}
            selected = profiles or list(available)
            if len(set(selected))!=len(selected) or set(selected)-available.keys():
                raise ExportError('Unknown/duplicate selected profiles')
            versions = {p['world']:p['version'] for p in available.values()}
            identifier = hashlib.sha256((meta['snapshotId']+VERSION+','.join(sorted(selected))).encode()).hexdigest()[:24]
            destination = output/identifier
            if destination.exists():
                raise ExportError(f'Catalog release already exists: {destination}; use a different --output to rebuild')
            with tempfile.TemporaryDirectory(prefix='.catalogs-',dir=output) as staging:
                stage = Path(staging)
                manifest = {'schemaVersion':VERSION,'snapshotId':meta['snapshotId'],'releaseId':identifier,
                            'profiles':[],'warnings':[], 'builtAtUnix':time.time()}
                for profile_id in selected:
                    profile = available[profile_id]
                    folder = stage/profile_id
                    folder.mkdir()
                    store = Store(db,profile_id)
                    decoder = CatalogDecoder(store,versions,meta['encoding'])
                    counts = {}
                    for tag,name in CATALOGS.items():
                        print(f'{profile_id}: decoding {name}...',flush=True)
                        rows = []
                        for key in store.keys_for(tag):
                            try:
                                row = decoder.parse(tag,key)
                                if row is None:
                                    continue
                                version_id,_,origin,winner = db.execute(SQL,(profile_id,tag,key)).fetchone()
                                row.update(key=key,recordType=tag,
                                    gameDataVersion={'world':profile['world'],'version':profile['version']},
                                    provenance={'originPlugin':origin,'winningPlugin':winner,'recordVersionId':version_id})
                                # Strict serialization rejects NaN/Infinity before publication.
                                json.dumps(row,allow_nan=False)
                                rows.append(row)
                            except (KeyError,ValueError) as exc:
                                raise ExportError(f'{profile_id}: {tag} {key}: {exc}') from exc
                        if tag=='BOOK':
                            # Prose is ~70% of the catalog and no calculator reads it. Keep it
                            # joinable by key in a separate file the app fetches only on demand.
                            texts=[{'key':row['key'],'text':row.pop('text','')} for row in rows]
                            write_json(folder/(BOOK_TEXT+'.json'),{'schemaVersion':VERSION,'snapshotId':meta['snapshotId'],
                                'profile':profile,'recordType':'BOOK_TEXT','records':texts})
                            counts[BOOK_TEXT]=len(texts)
                        write_json(folder/(name+'.json'),{'schemaVersion':VERSION,'snapshotId':meta['snapshotId'],
                            'profile':profile,'recordType':tag,'records':rows})
                        counts[name]=len(rows)
                        print(f'  {len(rows):,} records',flush=True)
                    # Fixed engine attribute IDs, names derived from profile GMSTs.
                    write_json(folder/'Attributes.json',{'schemaVersion':VERSION,'snapshotId':meta['snapshotId'],
                        'profile':profile,'recordType':'derived_attributes','records':[
                            {'id':a,'index':i,'name':decoder.gmsts.get('sattribute'+a,a.title())} for i,a in enumerate(ATTRIBUTES)]})
                    counts['Attributes']=8
                    for tag,key in sorted(decoder.links):
                        if db.execute(SQL,(profile_id,tag,key)).fetchone() is None:
                            manifest['warnings'].append({'profile':profile_id,'code':'missing_reference','recordType':tag,'key':key})
                    manifest['profiles'].append(profile|{'counts':counts})
                write_json(stage/'manifest.json',manifest)
                # Versioned directory, followed by an atomic active-release pointer.
                # A failure before pointer replacement leaves the prior release active.
                os.replace(stage,destination)
            pointer = output/'.current.tmp'
            write_json(pointer,{'releaseId':identifier,'manifest':identifier+'/manifest.json','snapshotId':meta['snapshotId']})
            os.replace(pointer,output/'current.json')
            print(f'Catalogs complete: {destination}\nCoverage warnings: {len(manifest["warnings"])}',flush=True)
            return destination
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--profile',action='append',choices=['vanilla','tr','tr_arce'])
    args=parser.parse_args(argv)
    try:
        root=load_config(ROOT/'foundation_config.json')[2]
        database=args.database or root/'game-data.sqlite'
        output=args.output or root/'catalogs'
        if output.resolve()==database.resolve() or database.resolve().is_relative_to(output.resolve()):
            raise ExportError('Catalog output must not contain or replace the foundation database')
        build(database,output,args.profile)
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; previous active catalog release is unchanged.')
        return 130
    except (ValueError,KeyError,OSError,sqlite3.Error) as exc:
        print(f'Catalog build failed: {exc}')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
