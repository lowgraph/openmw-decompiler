PRAGMA foreign_keys=ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE plugins (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
 path TEXT NOT NULL, byte_size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
 sha256 TEXT, masters_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE record_versions (
 id INTEGER PRIMARY KEY, plugin_id INTEGER NOT NULL REFERENCES plugins(id),
 ordinal INTEGER NOT NULL, file_offset INTEGER NOT NULL, record_type TEXT NOT NULL,
 record_key TEXT, display_id TEXT, deleted INTEGER NOT NULL,
 header_unknown INTEGER NOT NULL, header_flags INTEGER NOT NULL,
 payload BLOB NOT NULL, UNIQUE(plugin_id, ordinal)
);
CREATE INDEX record_identity ON record_versions(record_type, record_key);
CREATE TABLE reference_versions (
 id INTEGER PRIMARY KEY, plugin_id INTEGER NOT NULL REFERENCES plugins(id),
 record_id INTEGER NOT NULL REFERENCES record_versions(id), reference_key TEXT NOT NULL,
 source_cell_key TEXT NOT NULL, target_cell_key TEXT NOT NULL,
 object_id TEXT, deleted INTEGER NOT NULL, payload_offset INTEGER NOT NULL,
 payload_length INTEGER NOT NULL, moved INTEGER NOT NULL
);
CREATE INDEX reference_plugin ON reference_versions(plugin_id);
CREATE INDEX reference_identity ON reference_versions(reference_key);
CREATE TABLE profiles (id TEXT PRIMARY KEY, world TEXT NOT NULL, version TEXT NOT NULL, arce INTEGER NOT NULL);
CREATE TABLE profile_plugins (
 profile_id TEXT NOT NULL REFERENCES profiles(id), plugin_id INTEGER NOT NULL REFERENCES plugins(id),
 load_order INTEGER NOT NULL, PRIMARY KEY(profile_id, plugin_id), UNIQUE(profile_id, load_order)
);
CREATE TABLE resolved_records (
 profile_id TEXT NOT NULL REFERENCES profiles(id), record_type TEXT NOT NULL, record_key TEXT NOT NULL,
 origin_plugin_id INTEGER NOT NULL REFERENCES plugins(id), winner_id INTEGER NOT NULL REFERENCES record_versions(id),
 PRIMARY KEY(profile_id, record_type, record_key)
);
CREATE TABLE resolved_references (
 profile_id TEXT NOT NULL REFERENCES profiles(id), reference_key TEXT NOT NULL,
 origin_plugin_id INTEGER NOT NULL REFERENCES plugins(id), winner_id INTEGER NOT NULL REFERENCES reference_versions(id),
 PRIMARY KEY(profile_id, reference_key)
);
CREATE VIEW live_records AS
 SELECT r.profile_id, r.record_type, r.record_key, r.origin_plugin_id,
        v.id AS version_id, v.plugin_id AS winning_plugin_id, v.display_id
 FROM resolved_records r JOIN record_versions v ON v.id=r.winner_id WHERE v.deleted=0;
CREATE VIEW live_references AS
 SELECT r.profile_id, r.reference_key, r.origin_plugin_id, v.id AS version_id,
        v.plugin_id AS winning_plugin_id, v.target_cell_key, v.object_id
 FROM resolved_references r JOIN reference_versions v ON v.id=r.winner_id
 LEFT JOIN resolved_records c ON c.profile_id=r.profile_id AND c.record_type='CELL' AND c.record_key=v.target_cell_key
 LEFT JOIN record_versions cv ON cv.id=c.winner_id
 WHERE v.deleted=0 AND COALESCE(cv.deleted,0)=0;
