"""User-owned notebooks. Membership never duplicates a word's review schedule."""
from datetime import date, datetime


def migrate(db):
    first = not db.execute("SELECT 1 FROM sqlite_master WHERE name='notebooks'").fetchone()
    db.execute("CREATE TABLE IF NOT EXISTS notebooks(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,position INTEGER NOT NULL DEFAULT 0)")
    db.execute("CREATE TABLE IF NOT EXISTS notebook_words(notebook_id INTEGER NOT NULL,word TEXT NOT NULL,PRIMARY KEY(notebook_id,word))")
    db.execute("CREATE INDEX IF NOT EXISTS idx_notebook_word ON notebook_words(word)")
    if 'notebook_id' not in {r[1] for r in db.execute('PRAGMA table_info(import_batches)')}:
        db.execute('ALTER TABLE import_batches ADD COLUMN notebook_id INTEGER NOT NULL DEFAULT 1')
    db.execute("INSERT OR IGNORE INTO notebooks(id,name,position) VALUES(1,'默认单词本',0)")
    if first:
        db.execute('INSERT OR IGNORE INTO notebook_words SELECT 1,word FROM words')


def name_value(name):
    name = name.strip()
    if not 1 <= len(name) <= 40 or name == '全部单词':
        raise ValueError('名称需为 1–40 个字符')
    return name


def create(db, name):
    with db:
        return db.execute('INSERT INTO notebooks(name,position) VALUES(?,(SELECT COALESCE(MAX(position),0)+1 FROM notebooks))', (name_value(name),)).lastrowid


def rename(db, book, name):
    if book == 1:
        raise ValueError('默认单词本保留固定名称')
    with db:
        db.execute('UPDATE notebooks SET name=? WHERE id=?', (name_value(name), book))


def require(db, book):
    if not db.execute('SELECT 1 FROM notebooks WHERE id=?', (book,)).fetchone():
        raise ValueError('单词本不存在，请重新选择')


def add(db, book, words):
    require(db, book)
    with db:
        for word in words:
            if not db.execute('SELECT 1 FROM words WHERE word=?', (word,)).fetchone():
                raise ValueError('单词不存在：' + word)
            db.execute('INSERT OR IGNORE INTO notebook_words VALUES(?,?)', (book, word))


def remove(db, book, words):
    require(db, book)
    with db:
        db.executemany('DELETE FROM notebook_words WHERE notebook_id=? AND word=?', [(book, w) for w in words])
        # Keep every word reachable, without re-adding removed memberships at startup.
        db.execute('INSERT OR IGNORE INTO notebook_words SELECT 1,word FROM words w WHERE NOT EXISTS(SELECT 1 FROM notebook_words n WHERE n.word=w.word)')


def delete(db, book):
    if book == 1:
        raise ValueError('默认单词本不能删除')
    with db:
        db.execute('DELETE FROM notebook_words WHERE notebook_id=?', (book,))
        db.execute('UPDATE import_batches SET notebook_id=1 WHERE notebook_id=?', (book,))
        db.execute('DELETE FROM notebooks WHERE id=?', (book,))
        db.execute('INSERT OR IGNORE INTO notebook_words SELECT 1,word FROM words w WHERE NOT EXISTS(SELECT 1 FROM notebook_words n WHERE n.word=w.word)')


def move(db, book, direction):
    if direction not in (-1, 1):
        raise ValueError('排序方向无效')
    ids = [r[0] for r in db.execute('SELECT id FROM notebooks ORDER BY position,id')]
    index = ids.index(book); other = index + direction
    if 0 <= other < len(ids):
        ids[index], ids[other] = ids[other], ids[index]
        with db:
            db.executemany('UPDATE notebooks SET position=? WHERE id=?', list(enumerate(ids)))


def stats(db):
    return [dict(r) for r in db.execute('''SELECT n.id,n.name,n.position,COUNT(w.word) total,
        COALESCE(SUM(CASE WHEN w.word IS NOT NULL AND w.learned_at IS NULL THEN 1 ELSE 0 END),0) unlearned,
        COALESCE(SUM(CASE WHEN w.learned_at IS NOT NULL AND w.due<=? THEN 1 ELSE 0 END),0) due
        FROM notebooks n LEFT JOIN notebook_words nw ON nw.notebook_id=n.id
        LEFT JOIN words w ON w.word=nw.word GROUP BY n.id ORDER BY n.position,n.id''', (date.today().isoformat(),))]


def words(db, book=0, query='', due_only=False):
    clauses=[]; args=[]
    if book:
        clauses.append('EXISTS(SELECT 1 FROM notebook_words nw WHERE nw.word=w.word AND nw.notebook_id=?)'); args.append(book)
    if due_only:
        clauses.append('w.learned_at IS NOT NULL AND w.due<=?'); args.append(date.today().isoformat())
    sql='SELECT w.* FROM words w'+(' WHERE '+' AND '.join(clauses) if clauses else '')+' ORDER BY w.word'
    query=query.strip().lower(); result=[]
    for row in db.execute(sql, args):
        import json
        meaning=json.loads(row['content']).get('meaning','')
        scenes=' '.join(r[0] for r in db.execute('SELECT s.name FROM scenes s JOIN scene_words sw ON sw.scene_id=s.id WHERE sw.word=?', (row['word'],)))
        if not query or query in (row['word']+' '+meaning+' '+scenes).lower(): result.append(dict(row))
    return result
