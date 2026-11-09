"""Tkinter interaction checks; run on Windows or under an X display."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
import app
import notebooks

@unittest.skipUnless(os.name=='nt' or os.environ.get('DISPLAY'),'Desktop UI needs a display')
class DesktopUITests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.ui=app.App(Path(self.folder.name)/'test.db')
        self.book=notebooks.create(self.ui.db,'建筑英语300词')
        for word,meaning in [('inspection','检查'),('passport','护照'),('concrete','混凝土')]:
            self.ui.db.execute('INSERT INTO words(word,content,stage,due) VALUES(?,?,0,?)',(word,json.dumps({'meaning':meaning}),'2026-01-01'))
        self.ui.db.commit();notebooks.add(self.ui.db,self.book,['inspection','concrete']);notebooks.add(self.ui.db,1,['passport']);self.ui.refresh_all();self.ui.update()
        self.ui.book_choice.set('建筑英语300词');self.ui.select_book()
    def tearDown(self):self.ui.close();self.folder.cleanup()
    def test_search_and_learning_queue_stay_inside_book_and_query(self):
        self.assertEqual(list(self.ui.word_tree.get_children()),['concrete','inspection'])
        self.ui.word_search.set('检查');self.ui.refresh_words()
        self.assertEqual(list(self.ui.word_tree.get_children()),['inspection'])
        with patch.object(self.ui,'word_detail') as detail:
            self.ui.start_learning_sequence();detail.assert_called_once_with('inspection')
        with patch.object(app.messagebox,'showinfo'):self.ui.mark_familiar_next('inspection')
        row=self.ui.db.execute("SELECT learned_at FROM words WHERE word='inspection'").fetchone()
        self.assertIsNotNone(row[0]);self.assertEqual(self.ui.learning_scope,[])
    def test_existing_only_import_needs_no_ai_and_keeps_progress(self):
        before=tuple(self.ui.db.execute("SELECT stage,due,mastery FROM words WHERE word='passport'").fetchone())
        self.ui.preview=({'items':[],'existing':[{'word':'passport'}]},'paste',self.book)
        with patch.object(app.messagebox,'showinfo'),patch.object(self.ui,'classify') as classify:
            self.ui.start_import();classify.assert_not_called()
        self.assertIn('passport',[r['word'] for r in notebooks.words(self.ui.db,self.book)])
        self.assertEqual(tuple(self.ui.db.execute("SELECT stage,due,mastery FROM words WHERE word='passport'").fetchone()),before)
    def test_review_scope_switch_and_book_create_rename(self):
        self.ui.review_current_book();self.assertEqual(self.ui.review_book_id,self.book)
        self.ui.review_book_choice.set('全部单词');self.ui.select_review_book();self.assertEqual(self.ui.review_book_id,0)
        with patch.object(app.simpledialog,'askstring',return_value='小说生词'):self.ui.create_book()
        self.assertEqual(self.ui.book_choice.get(),'小说生词')
        with patch.object(app.simpledialog,'askstring',return_value='阅读生词'):self.ui.rename_book()
        self.assertEqual(self.ui.import_book_box.cget('values')[-1],'阅读生词')

if __name__=='__main__':unittest.main()
