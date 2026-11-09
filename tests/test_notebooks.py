import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
import core
import notebooks
import backup

class NotebookTests(unittest.TestCase):
    def setUp(self):self.db=core.connect(':memory:')
    def tearDown(self):self.db.close()
    def word(self,word='inspection',stage=3):
        with self.db:
            self.db.execute('INSERT INTO words(word,content,stage,due,mastery,learned_at) VALUES(?,?,?,?,?,?)',(word,json.dumps({'word':word,'meaning':'检查'}),stage,date.today().isoformat(),1 if stage else 0,'2026-01-01' if stage else None))
        notebooks.add(self.db,1,[word])
    def test_legacy_migration_once_preserves_membership_and_schedule(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'old.db';db=sqlite3.connect(path)
            db.execute('CREATE TABLE words(word TEXT PRIMARY KEY,content TEXT NOT NULL,stage INTEGER NOT NULL,due TEXT NOT NULL)')
            db.execute('INSERT INTO words VALUES(?,?,?,?)',('inspection','{"meaning":"检查"}',5,'2030-01-02'));db.commit();db.close()
            db=core.connect(path);book=notebooks.create(db,'建筑英语');notebooks.add(db,book,['inspection']);notebooks.remove(db,1,['inspection']);db.close()
            db=core.connect(path)
            self.assertEqual([r[0] for r in db.execute('SELECT notebook_id FROM notebook_words')],[book])
            row=db.execute('SELECT stage,due FROM words').fetchone();self.assertEqual(tuple(row),(5,'2030-01-02'));db.close()
    def test_shared_schedule_idempotent_add_and_scoped_due(self):
        self.word();self.word('passport',0);a=notebooks.create(self.db,'工地');b=notebooks.create(self.db,'工作')
        notebooks.add(self.db,a,['inspection']);notebooks.add(self.db,b,['inspection']);notebooks.add(self.db,b,['inspection'])
        self.assertEqual(len(notebooks.words(self.db,a,due_only=True)),1)
        self.db.execute('UPDATE words SET due=? WHERE word=?',('2030-01-01','inspection'));self.db.commit()
        self.assertEqual(notebooks.words(self.db,b,due_only=True),[])
        self.assertEqual(self.db.execute('SELECT count(*) FROM words').fetchone()[0],2)
    def test_delete_preserves_words_and_returns_orphans_to_default(self):
        self.word();book=notebooks.create(self.db,'测试');notebooks.add(self.db,book,['inspection']);notebooks.remove(self.db,1,['inspection'])
        batch=core.create_batch(self.db,core.parse_import('passport'),'paste',book)
        notebooks.delete(self.db,book)
        self.assertEqual(len(notebooks.words(self.db,1)),1)
        self.assertEqual(self.db.execute('SELECT notebook_id FROM import_batches WHERE id=?',(batch,)).fetchone()[0],1)
        with self.assertRaises(ValueError):notebooks.delete(self.db,1)
    def test_remove_only_membership_keeps_word_accessible(self):
        self.word();notebooks.remove(self.db,1,['inspection'])
        self.assertEqual(len(notebooks.words(self.db,1)),1)
    def test_names_order_and_empty_counts(self):
        a=notebooks.create(self.db,'甲');b=notebooks.create(self.db,'乙');notebooks.move(self.db,b,-1)
        self.assertEqual([r['id'] for r in notebooks.stats(self.db)],[1,b,a])
        self.assertEqual(notebooks.stats(self.db)[1]['unlearned'],0)
        notebooks.rename(self.db,a,'建筑英语')
        with self.assertRaises(ValueError):notebooks.create(self.db,'全部单词')
        with self.assertRaises(sqlite3.IntegrityError):notebooks.create(self.db,'建筑英语')
    def test_add_invalid_word_rolls_back_whole_selection(self):
        self.word();book=notebooks.create(self.db,'测试')
        with self.assertRaises(ValueError):notebooks.add(self.db,book,['inspection','missing'])
        self.assertEqual(notebooks.words(self.db,book),[])
    def classification(self,book):
        preview=core.parse_import('passport: 护照');batch=core.create_batch(self.db,preview,'paste',book)
        card={'word':'passport',**{f:'内容' for f in core.FIELDS}}
        core.save_classification(self.db,batch,{'cards':[card],'scenes':[{'name':'机场','members':[{'word':'passport','reason':'通关'}]}],'links':[],'unclassified':[]})
        return batch
    def test_classification_uses_persisted_target_and_filter(self):
        self.word();book=notebooks.create(self.db,'旅游');self.classification(book)
        self.assertEqual([r['word'] for r in notebooks.words(self.db,book,'机场')],['passport'])
        self.assertEqual(notebooks.words(self.db,book,'inspection'),[])
        self.assertEqual(notebooks.stats(self.db)[1]['unlearned'],1)
    def test_full_backup_roundtrip_all_tables_and_profiles_untouched(self):
        self.word();book=notebooks.create(self.db,'旅游');batch=self.classification(book)
        core.save_chunk(self.db,batch,0,{'cards':[]});core.save_debug_response(self.db,batch,0,'有效','{}')
        core.save_memory_turn(self.db,'inspection','问题','回答',{'score':80},'{}')
        core.save_scene_summary(self.db,{'name':'机场','fingerprint':'x'},{'overview':'机场'},'{}')
        core.save_review_attempt(self.db,'inspection','问题','回答',{'rating':1,'verdict':'正确','feedback':'好','explanation':'解释'},'{}')
        before=backup.export_data(self.db)
        self.assertNotIn('api_profiles',before['tables']);self.assertNotIn('source',before['tables']['words'][0])
        other=core.connect(':memory:')
        try:
            other.execute("UPDATE api_profiles SET model='keep-me'");other.commit();backup.restore(other,json.loads(json.dumps(before)))
            self.assertEqual(backup.export_data(other)['tables'],before['tables'])
            self.assertEqual(other.execute('SELECT model FROM api_profiles').fetchone()[0],'keep-me')
        finally:other.close()
    def test_corrupt_backups_never_touch_destination(self):
        self.word();before=backup.export_data(self.db)
        variants=[]
        broken=copy.deepcopy(before);del broken['tables']['scenes'];variants.append(broken)
        broken=copy.deepcopy(before);broken['tables']['notebook_words'][0]['word']='missing';variants.append(broken)
        broken=copy.deepcopy(before);broken['tables']['words'][0]['due']='bad-date';variants.append(broken)
        broken=copy.deepcopy(before);broken['tables']['words'][0]['stage']=9;variants.append(broken)
        broken=copy.deepcopy(before);broken['tables']['words'].append(broken['tables']['words'][0].copy());variants.append(broken)
        for bad in variants:
            with self.assertRaises((ValueError,sqlite3.Error)):backup.restore(self.db,bad)
            self.assertEqual(backup.export_data(self.db)['tables'],before['tables'])
    def test_legacy_merge_keeps_current_progress_and_is_atomic(self):
        self.word();backup.import_legacy(self.db,[{'word':'inspection','content':{'meaning':'新释义'},'stage':0}])
        self.assertEqual(self.db.execute('SELECT stage FROM words').fetchone()[0],3)
        with self.assertRaises(ValueError):backup.import_legacy(self.db,[{'word':'passport','content':{}},{'word':'bad123','content':{}}])
        self.assertIsNone(self.db.execute("SELECT 1 FROM words WHERE word='passport'").fetchone())
    def test_restore_to_legacy_schema_with_required_source(self):
        self.word();data=backup.export_data(self.db)
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.execute("CREATE TABLE words(word TEXT PRIMARY KEY,content TEXT NOT NULL,source TEXT NOT NULL,stage INTEGER NOT NULL,due TEXT NOT NULL)")
        core.migrate(db)
        try:
            backup.restore(db,data)
            backup.import_legacy(db,[{'word':'passport','content':{'meaning':'护照'}}])
            self.assertEqual(db.execute('SELECT count(*) FROM words').fetchone()[0],2)
        finally:db.close()
    def test_android_and_desktop_backup_schemas_match(self):
        import re
        java=(Path(__file__).resolve().parents[1]/'app/src/main/java/com/gongdi/wordcards/Backup.java').read_text()
        self.assertEqual(dict(re.findall(r'TABLES.put\("([^"]+)","([^"]+)"\)',java)),backup.TABLES)

if __name__=='__main__':unittest.main()
