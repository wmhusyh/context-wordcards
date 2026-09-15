import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"desktop"))
import core

class CoreTests(unittest.TestCase):
    def test_parser_handles_meanings_duplicates_empty_and_errors(self):
        result=core.parse_import("Airport\npassport: 护照\n\npassport\n错误123\ncheck in\t办理登机")
        self.assertEqual([x["word"] for x in result["items"]],["airport","passport","check in"])
        self.assertEqual(result["items"][1]["meaning"],"护照")
        self.assertEqual(len(result["duplicates"]),1)
        self.assertEqual(len(result["errors"]),1)
        self.assertGreaterEqual(result["empty_lines"],1)

    def test_csv_header_and_quotes(self):
        result=core.parse_import('word,meaning\n"boarding pass","登机牌"\npassport,护照',True)
        self.assertEqual([(x["word"],x["meaning"]) for x in result["items"]],[("boarding pass","登机牌"),("passport","护照")])
        self.assertEqual(result["errors"],[])

    def test_migration_preserves_legacy_word_and_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"legacy.db";db=sqlite3.connect(path)
            db.execute("CREATE TABLE words(word TEXT PRIMARY KEY,content TEXT NOT NULL,source TEXT NOT NULL,stage INTEGER NOT NULL,due TEXT NOT NULL)")
            db.execute("INSERT INTO words VALUES(?,?,?,?,?)",("legacy",json.dumps({"meaning":"旧词"}),"api",3,"2030-01-02"));db.commit();db.close()
            migrated=core.connect(path);row=migrated.execute("SELECT * FROM words WHERE word='legacy'").fetchone()
            self.assertEqual((row["stage"],row["due"],row["mastery"]),(3,"2030-01-02",0))
            for table in ("import_batches","import_items","scenes","scene_words","unclassified","word_links"):self.assertIsNotNone(migrated.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())
            migrated.close()

    def test_classification_and_links_are_persistent_and_adjustable(self):
        with tempfile.TemporaryDirectory() as folder:
            db=core.connect(Path(folder)/"words.db")
            old={"meaning":"旅行","part_of_speech":"noun","explanation":"","example":"","translation":"","memory":"","quiz":"","answer":""}
            db.execute("INSERT INTO words(word,content,source,stage,due,mastery) VALUES(?,?,?,?,?,?)",("travel",json.dumps(old),"legacy",4,"2030-01-01",2));db.commit()
            preview=core.parse_import("passport: 护照\nboarding pass: 登机牌\nknife: 刀")
            batch=core.create_batch(db,preview,"paste")
            cards=[]
            for item in preview["items"]:
                cards.append({"word":item["word"],"meaning":item["meaning"],"part_of_speech":"noun","explanation":"simple","example":"example","translation":"翻译","memory":"记忆","quiz":"测试","answer":"answer"})
            result={"cards":cards,"scenes":[{"name":"机场值机","members":[{"word":"passport","reason":"办理值机时用于核验身份"},{"word":"boarding pass","reason":"完成值机后用于登机"}]},{"name":"厨房做饭","members":[{"word":"knife","reason":"备菜时用于切食材"}]},{"name":"旅行准备","members":[{"word":"passport","reason":"出境旅行前需要准备"}]}],"unclassified":[],"links":[{"new_word":"passport","old_word":"travel","relation":"相关场景","reason":"护照常用于旅行","example":"Keep your passport safe when you travel."}]}
            core.save_classification(db,batch,result)
            self.assertEqual(db.execute("SELECT status FROM import_batches WHERE id=?",(batch,)).fetchone()[0],"draft")
            self.assertEqual(db.execute("SELECT count(*) FROM scene_words WHERE word='passport'").fetchone()[0],2)
            self.assertEqual(db.execute("SELECT old_word FROM word_links WHERE new_word='passport'").fetchone()[0],"travel")
            with db:
                db.execute("UPDATE scenes SET name='机场手续',user_modified=1 WHERE name='机场值机'")
                db.execute("UPDATE import_batches SET status='confirmed' WHERE id=?",(batch,))
            db.close();reopened=core.connect(Path(folder)/"words.db")
            self.assertEqual(reopened.execute("SELECT name FROM scenes WHERE user_modified=1").fetchone()[0],"机场手续")
            self.assertEqual(reopened.execute("SELECT status FROM import_batches WHERE id=?",(batch,)).fetchone()[0],"confirmed")
            reopened.close()

    def test_schema_validation_rejects_bad_members_and_links(self):
        words=[{"word":"passport","meaning":"护照"}];known=[{"word":"travel","meaning":"旅行","mastery":2,"scenes":[]}]
        card={"word":"passport",**{f:"x" for f in core.FIELDS}}
        valid={"cards":[card],"scenes":[{"name":"机场出行","members":[{"word":"passport","reason":"出境所需"}]}],"unclassified":[],"links":[]}
        core.validate_result(valid,words,known)
        invalid=json.loads(json.dumps(valid));invalid["scenes"][0]["members"][0]["word"]="invented"
        with self.assertRaises(ValueError):core.validate_result(invalid,words,known)
        invalid=json.loads(json.dumps(valid));invalid["links"]=[{"new_word":"passport","old_word":"invented","reason":"x"}]
        with self.assertRaises(ValueError):core.validate_result(invalid,words,known)

    def test_endpoint_schedule_and_dpapi(self):
        self.assertEqual(core.endpoint("https://api.example.com/v1/","responses"),"https://api.example.com/v1/responses")
        self.assertEqual(core.endpoint("https://api.example.com/v1/responses","chat"),"https://api.example.com/v1/chat/completions")
        with self.assertRaises(ValueError):core.endpoint("http://example.com/v1","chat")
        self.assertEqual(core.schedule(0,1,date(2026,12,31)),(1,"2027-01-01"))
        secret="test-key-for-local-roundtrip";self.assertEqual(core.unprotect(core.protect(secret)),secret)

if __name__=="__main__":unittest.main(verbosity=2)
