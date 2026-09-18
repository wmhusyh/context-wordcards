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
            self.assertEqual((row["stage"],row["due"],row["mastery"]),(3,"2030-01-02",0));self.assertIsNotNone(row["learned_at"])
            for table in ("import_batches","import_items","scenes","scene_words","unclassified","word_links","classification_chunks","api_debug_responses","review_attempts","scene_summaries","memory_chat"):self.assertIsNotNone(migrated.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())
            migrated.close()

    def test_migration_converts_mastered_to_familiar_without_losing_schedule(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"old-state.db";db=core.connect(path)
            db.execute("INSERT INTO words(word,content,stage,due,mastery,learned_at) VALUES(?,?,?,?,?,?)",("known",json.dumps({"meaning":"知道"}),5,"2030-04-06",2,"2030-01-01T08:00:00"));db.commit();db.close()
            migrated=core.connect(path);row=migrated.execute("SELECT mastery,stage,due,learned_at FROM words WHERE word='known'").fetchone()
            self.assertEqual((row["mastery"],row["stage"],row["due"],row["learned_at"]),(1,5,"2030-04-06","2030-01-01T08:00:00"));migrated.close()

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
            self.assertIsNone(db.execute("SELECT learned_at FROM words WHERE word='passport'").fetchone()[0])
            grouped=core.all_scenes(db);self.assertEqual({x["name"] for x in grouped},{"机场值机","厨房做饭","旅行准备"})
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
        self.assertEqual(core.schedule(0,1,date(2026,12,31)),(1,"2027-01-01"));self.assertEqual(core.schedule(7,1,date(2026,12,31)),(7,"2027-04-30"));self.assertEqual(core.schedule(3,2,date(2026,12,31)),(2,"2027-01-01"))
        secret="test-key-for-local-roundtrip";self.assertEqual(core.unprotect(core.protect(secret)),secret)

    def test_responses_verification_accepts_token_limited_result(self):
        core.validate_verification_envelope({"status":"incomplete"},"responses")
        with self.assertRaises(ValueError):core.validate_verification_envelope({"status":"failed"},"responses")

    def test_chunk_cache_and_scene_merge(self):
        with tempfile.TemporaryDirectory() as folder:
            db=core.connect(Path(folder)/"words.db");batch=core.create_batch(db,core.parse_import("passport\nboarding pass"),"paste")
            first={"cards":[{"word":"passport"}],"scenes":[{"name":"机场值机","members":[{"word":"passport","reason":"核验身份"}]}],"unclassified":[],"links":[]}
            second={"cards":[{"word":"boarding pass"}],"scenes":[{"name":"机场值机","members":[{"word":"boarding pass","reason":"用于登机"}]}],"unclassified":[],"links":[]}
            core.save_chunk(db,batch,0,first);self.assertEqual(core.load_chunk(db,batch,0),first)
            merged=core.merge_classification(core.empty_classification(),first);core.merge_classification(merged,second)
            self.assertEqual(len(merged["scenes"]),1);self.assertEqual({x["word"] for x in merged["scenes"][0]["members"]},{"passport","boarding pass"})
            core.clear_chunks(db,batch);self.assertIsNone(core.load_chunk(db,batch,0));db.close()

    def test_debug_response_and_invalid_optional_links(self):
        with tempfile.TemporaryDirectory() as folder:
            db=core.connect(Path(folder)/"words.db")
            content=json.dumps({"meaning":"旅行"},ensure_ascii=False)
            db.executemany("INSERT INTO words(word,content,source,stage,due,mastery) VALUES(?,?,?,?,?,?)",[("travel",content,"legacy",3,"2030-01-01",2),("passport",content,"legacy",0,"2030-01-01",0)]);db.commit()
            whole=[{"word":"passport","meaning":"护照"},{"word":"boarding pass","meaning":"登机牌"}];chunk=[whole[0]]
            self.assertEqual([x["word"] for x in core.known_words(db,excluded={x["word"] for x in whole})],["travel"])
            result={"links":[{"new_word":"passport","old_word":"travel","reason":"旅行需要护照"},{"new_word":"passport","old_word":"boarding pass","reason":"同批新词"},{"new_word":"passport","old_word":"missing","reason":"不存在"}]}
            self.assertEqual(core.sanitize_links(db,result,chunk,whole),2);self.assertEqual(result["links"][0]["old_word"],"travel")
            core.save_debug_response(db,9,0,"有效，已忽略 2 条无效关联",'{"ok":true}')
            logs=core.debug_responses(db,9);self.assertEqual((logs[0]["status"],logs[0]["content"]),("有效，已忽略 2 条无效关联",'{"ok":true}'));db.close()

    def test_review_evaluation_parsing_and_history(self):
        result={"rating":2,"verdict":"部分正确","feedback":"词义正确，例句搭配需修改","explanation":"表示办理登记手续。","suggested_answer":"Check in means to register. I check in at the hotel."}
        envelope=json.dumps({"choices":[{"finish_reason":"stop","message":{"content":json.dumps(result,ensure_ascii=False)}}]},ensure_ascii=False)
        self.assertEqual(core.parse_review_evaluation(envelope,"chat")["rating"],2)
        with tempfile.TemporaryDirectory() as folder:
            db=core.connect(Path(folder)/"words.db");core.save_review_attempt(db,"check in","question","answer",result,envelope)
            row=db.execute("SELECT rating,verdict FROM review_attempts WHERE word='check in'").fetchone();self.assertEqual(tuple(row),(2,"部分正确"));db.close()

    def test_scene_summary_and_memory_chat_are_cached(self):
        scene_result={"overview":"机场办理手续","connections":"护照用于核验，登机牌用于登机","differences":"证件与通行凭证不同","memory_path":"先出示护照，再领取登机牌"}
        coach={"score":86,"remembered":True,"verdict":"已经记住","feedback":"含义和用法正确","explanation":"passport 指护照","next_question":"请说一个常见搭配"}
        def envelope(value):return json.dumps({"choices":[{"finish_reason":"stop","message":{"content":json.dumps(value,ensure_ascii=False)}}]},ensure_ascii=False)
        self.assertEqual(core.parse_scene_summary(envelope(scene_result),"chat")["overview"],"机场办理手续");self.assertTrue(core.parse_memory_coach(envelope(coach),"chat")["remembered"])
        with tempfile.TemporaryDirectory() as folder:
            db=core.connect(Path(folder)/"words.db");scene={"name":"机场值机","fingerprint":"abc","members":[]};core.save_scene_summary(db,scene,scene_result,envelope(scene_result));self.assertEqual(core.scene_summary(db,"机场值机","abc")["differences"],"证件与通行凭证不同")
            core.save_memory_turn(db,"passport","问题","回答",coach,envelope(coach));turns=core.memory_turns(db,"passport");self.assertEqual((turns[0]["result"]["score"],turns[0]["answer"]),(86,"回答"));db.close()

if __name__=="__main__":unittest.main(verbosity=2)
