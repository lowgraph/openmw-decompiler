PRAGMA foreign_keys=ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE profiles(id TEXT PRIMARY KEY,world TEXT NOT NULL,version TEXT NOT NULL,arce INTEGER NOT NULL);
CREATE TABLE service_flags(bit INTEGER PRIMARY KEY,code TEXT NOT NULL,kind TEXT NOT NULL);
CREATE TABLE providers(version_id INTEGER PRIMARY KEY,actor_key TEXT NOT NULL,record_type TEXT NOT NULL,name TEXT NOT NULL,plugin TEXT NOT NULL,script_key TEXT,services_raw INTEGER,unknown_service_bits INTEGER,stats_json TEXT NOT NULL);
CREATE TABLE profile_providers(profile_id TEXT REFERENCES profiles(id),actor_key TEXT NOT NULL,version_id INTEGER REFERENCES providers(version_id),origin_plugin TEXT NOT NULL,PRIMARY KEY(profile_id,actor_key));
CREATE INDEX provider_revision ON profile_providers(version_id,profile_id);
CREATE TABLE provider_services(provider_version_id INTEGER REFERENCES providers(version_id),service_bit INTEGER REFERENCES service_flags(bit),PRIMARY KEY(provider_version_id,service_bit));
CREATE TABLE transport_destinations(provider_version_id INTEGER REFERENCES providers(version_id),entry_index INTEGER NOT NULL,cell_name TEXT,x REAL NOT NULL,y REAL NOT NULL,z REAL NOT NULL,rx REAL NOT NULL,ry REAL NOT NULL,rz REAL NOT NULL,PRIMARY KEY(provider_version_id,entry_index));
CREATE TABLE cells(profile_id TEXT REFERENCES profiles(id),cell_key TEXT NOT NULL,name TEXT,interior INTEGER NOT NULL,grid_x INTEGER,grid_y INTEGER,region_key TEXT,synthetic INTEGER NOT NULL,PRIMARY KEY(profile_id,cell_key));
CREATE TABLE profile_destinations(profile_id TEXT REFERENCES profiles(id),provider_version_id INTEGER,entry_index INTEGER,cell_key TEXT,status TEXT NOT NULL,PRIMARY KEY(profile_id,provider_version_id,entry_index),FOREIGN KEY(provider_version_id,entry_index) REFERENCES transport_destinations(provider_version_id,entry_index));
CREATE TABLE provider_locations(profile_id TEXT REFERENCES profiles(id),reference_key TEXT,placement_version_id INTEGER NOT NULL,provider_version_id INTEGER REFERENCES providers(version_id),cell_key TEXT NOT NULL,x REAL,y REAL,z REAL,PRIMARY KEY(profile_id,reference_key),FOREIGN KEY(profile_id,cell_key) REFERENCES cells(profile_id,cell_key));
CREATE INDEX provider_locations_actor ON provider_locations(profile_id,provider_version_id);
CREATE TABLE door_links(placement_version_id INTEGER PRIMARY KEY,reference_key TEXT NOT NULL,door_key TEXT NOT NULL,plugin TEXT NOT NULL,from_cell_key TEXT NOT NULL,cell_name TEXT,x REAL NOT NULL,y REAL NOT NULL,z REAL NOT NULL,rx REAL NOT NULL,ry REAL NOT NULL,rz REAL NOT NULL,source_x REAL,source_y REAL,source_z REAL,details_json TEXT NOT NULL);
CREATE TABLE profile_door_links(profile_id TEXT REFERENCES profiles(id),placement_version_id INTEGER REFERENCES door_links(placement_version_id),to_cell_key TEXT,status TEXT NOT NULL,PRIMARY KEY(profile_id,placement_version_id));
CREATE TABLE warnings(profile_id TEXT,code TEXT NOT NULL,source_key TEXT NOT NULL,detail TEXT NOT NULL);
CREATE VIEW travel_edges AS
 SELECT l.profile_id,'transport' AS kind,l.reference_key AS source_reference_key,
 l.placement_version_id AS source_placement_version_id,l.provider_version_id,d.entry_index,
 l.cell_key AS from_cell_key,r.cell_key AS to_cell_key,r.status AS destination_status,
 l.x AS source_x,l.y AS source_y,l.z AS source_z,d.x AS destination_x,d.y AS destination_y,d.z AS destination_z
 FROM provider_locations l JOIN transport_destinations d ON d.provider_version_id=l.provider_version_id
 JOIN profile_destinations r ON r.profile_id=l.profile_id AND r.provider_version_id=d.provider_version_id AND r.entry_index=d.entry_index
 UNION ALL
 SELECT p.profile_id,'door',d.reference_key,d.placement_version_id,NULL,NULL,
 d.from_cell_key,p.to_cell_key,p.status,d.source_x,d.source_y,d.source_z,d.x,d.y,d.z
 FROM profile_door_links p JOIN door_links d ON d.placement_version_id=p.placement_version_id;
