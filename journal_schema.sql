PRAGMA foreign_keys=ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE profiles(id TEXT PRIMARY KEY,world TEXT NOT NULL,version TEXT NOT NULL,arce INTEGER NOT NULL);
CREATE TABLE topics(version_id INTEGER PRIMARY KEY,topic_key TEXT NOT NULL,editor_id TEXT NOT NULL,type_raw INTEGER,type_name TEXT NOT NULL,plugin TEXT NOT NULL);
CREATE TABLE profile_topics(profile_id TEXT REFERENCES profiles(id),topic_key TEXT NOT NULL,version_id INTEGER REFERENCES topics(version_id),origin_plugin TEXT NOT NULL,PRIMARY KEY(profile_id,topic_key));
CREATE TABLE responses(version_id INTEGER PRIMARY KEY,topic_key TEXT NOT NULL,info_key TEXT NOT NULL,editor_id TEXT NOT NULL,previous_info_key TEXT,next_info_key TEXT,type_raw INTEGER,value_raw INTEGER,npc_rank_raw INTEGER,gender_raw INTEGER,pc_rank_raw INTEGER,actor_key TEXT,race_key TEXT,class_key TEXT,faction_key TEXT,factionless INTEGER NOT NULL,pc_faction_key TEXT,cell_filter TEXT,sound TEXT,response_text TEXT NOT NULL,result_script TEXT,quest_status TEXT NOT NULL,plugin TEXT NOT NULL);
CREATE INDEX response_topic ON responses(topic_key,info_key);
CREATE TABLE profile_responses(profile_id TEXT REFERENCES profiles(id),topic_key TEXT NOT NULL,info_key TEXT NOT NULL,version_id INTEGER REFERENCES responses(version_id),origin_plugin TEXT NOT NULL,PRIMARY KEY(profile_id,topic_key,info_key),FOREIGN KEY(profile_id,topic_key) REFERENCES profile_topics(profile_id,topic_key));
CREATE INDEX response_revision ON profile_responses(version_id,profile_id);
CREATE TABLE conditions(response_version_id INTEGER REFERENCES responses(version_id),entry_index INTEGER NOT NULL,rule_raw TEXT NOT NULL,rule_hex TEXT NOT NULL,slot_raw TEXT,kind_raw TEXT,function_raw TEXT,comparison_raw TEXT,variable_raw TEXT,value_type TEXT,value_json TEXT,value_tag TEXT,value_hex TEXT,decode_status TEXT NOT NULL,PRIMARY KEY(response_version_id,entry_index));
CREATE TABLE scripts(version_id INTEGER PRIMARY KEY,script_key TEXT NOT NULL,editor_id TEXT NOT NULL,plugin TEXT NOT NULL,source_text TEXT,shorts_raw INTEGER,longs_raw INTEGER,floats_raw INTEGER,declared_bytecode_size INTEGER,actual_bytecode_size INTEGER NOT NULL,declared_variable_size INTEGER,actual_variable_size INTEGER NOT NULL,variable_names_json TEXT NOT NULL);
CREATE TABLE profile_scripts(profile_id TEXT REFERENCES profiles(id),script_key TEXT NOT NULL,version_id INTEGER REFERENCES scripts(version_id),origin_plugin TEXT NOT NULL,PRIMARY KEY(profile_id,script_key));
CREATE TABLE warnings(profile_id TEXT,record_type TEXT NOT NULL,record_key TEXT NOT NULL,code TEXT NOT NULL,detail TEXT NOT NULL);
CREATE VIEW quest_titles AS
 SELECT p.profile_id,p.topic_key,r.info_key,r.version_id,r.response_text AS title
 FROM profile_responses p JOIN responses r ON r.version_id=p.version_id
 JOIN profile_topics q ON q.profile_id=p.profile_id AND q.topic_key=p.topic_key
 JOIN topics t ON t.version_id=q.version_id WHERE t.type_raw=4 AND r.quest_status='name';
CREATE VIEW journal_entries AS
 SELECT p.profile_id,p.topic_key AS quest_key,r.info_key,r.version_id,r.value_raw AS journal_index,
 r.response_text,r.quest_status,r.result_script
 FROM profile_responses p JOIN responses r ON r.version_id=p.version_id
 JOIN profile_topics q ON q.profile_id=p.profile_id AND q.topic_key=p.topic_key
 JOIN topics t ON t.version_id=q.version_id WHERE t.type_raw=4 AND r.quest_status!='name';
CREATE VIEW quests AS
 SELECT q.profile_id,q.topic_key AS quest_key,t.editor_id,q.version_id,q.origin_plugin,t.plugin AS winning_plugin,
 CASE WHEN n.title_count=1 THEN n.title ELSE NULL END AS title,COALESCE(n.title_count,0) AS title_count
 FROM profile_topics q JOIN topics t ON t.version_id=q.version_id
 LEFT JOIN (SELECT profile_id,topic_key,count(DISTINCT title) AS title_count,min(title) AS title
            FROM quest_titles WHERE title!='' GROUP BY profile_id,topic_key) n
 ON n.profile_id=q.profile_id AND n.topic_key=q.topic_key WHERE t.type_raw=4;
