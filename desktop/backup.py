"""Portable, versioned vocabulary backups, excluding API settings and keys."""
import json
import sqlite3
from datetime import date, datetime

# Shared wire format with Android Backup.java. Column lists are also the import allowlist.
TABLES = {
    'words': 'word content stage due mastery created_batch learned_at',
    'notebooks': 'id name position',
    'notebook_words': 'notebook_id word',
    'import_batches': 'id created_at status source raw_count confirmed_at notebook_id',
    'import_items': 'id batch_id word meaning state error',
    'scenes': 'id batch_id name position user_modified',
    'scene_words': 'scene_id word reason',
    'unclassified': 'batch_id word reason',
    'word_links': 'id batch_id new_word old_word relation reason example',
    'classification_chunks': 'batch_id chunk_index result created_at',
    'api_debug_responses': 'id batch_id chunk_index status received_at content',
    'review_attempts': 'id word question answer rating verdict feedback explanation raw_response created_at',
    'scene_summaries': 'scene_name word_fingerprint summary raw_response updated_at',
    'memory_chat': 'id word question answer result raw_response created_at',
}


def export_data(db):
    # A single read transaction gives all tables the same snapshot.
    with db:
        db.execute('SAVEPOINT backup_snapshot')
        try:
            tables={table:[dict(r) for r in db.execute('SELECT '+','.join(cols.split())+' FROM '+table)] for table,cols in TABLES.items()}
        finally:
            db.execute('RELEASE backup_snapshot')
    return {'format':'context-wordcards','version':1,'created_at':datetime.now().isoformat(),'tables':tables}


def validate(data):
    import core
    if not isinstance(data,dict) or data.get('format')!='context-wordcards' or type(data.get('version')) is not int or data['version']!=1:
        raise ValueError('备份格式或版本不支持')
    tables=data.get('tables')
    if not isinstance(tables,dict) or set(tables)!=set(TABLES):
        raise ValueError('备份数据表不完整')
    stage=core.connect(':memory:')
    try:
        _replace(stage,tables)
        for row in stage.execute('SELECT * FROM words'):
            if core.normalize_word(row['word'])!=row['word'] or not isinstance(json.loads(row['content']),dict): raise ValueError('词卡内容无效')
            if type(row['stage']) is not int or not 0<=row['stage']<=7 or row['mastery'] not in (0,1):raise ValueError('复习进度无效')
            date.fromisoformat(row['due'])
        for row in stage.execute('SELECT name FROM notebooks'):
            if not row['name'].strip() or len(row['name'])>40:raise ValueError('单词本名称无效')
        if not stage.execute("SELECT 1 FROM notebooks WHERE id=1 AND name='默认单词本'").fetchone():raise ValueError('缺少默认单词本')
        checks=[
            'SELECT 1 FROM notebook_words n WHERE NOT EXISTS(SELECT 1 FROM words w WHERE w.word=n.word) OR NOT EXISTS(SELECT 1 FROM notebooks b WHERE b.id=n.notebook_id)',
            'SELECT 1 FROM words w WHERE NOT EXISTS(SELECT 1 FROM notebook_words n WHERE n.word=w.word)',
            'SELECT 1 FROM import_batches b WHERE NOT EXISTS(SELECT 1 FROM notebooks n WHERE n.id=b.notebook_id)',
            'SELECT 1 FROM scenes s WHERE NOT EXISTS(SELECT 1 FROM import_batches b WHERE b.id=s.batch_id)',
            'SELECT 1 FROM scene_words sw WHERE NOT EXISTS(SELECT 1 FROM scenes s WHERE s.id=sw.scene_id) OR NOT EXISTS(SELECT 1 FROM words w WHERE w.word=sw.word)',
        ]
        if any(stage.execute(sql).fetchone() for sql in checks):raise ValueError('备份关联不完整')
        for table,column in [('classification_chunks','result'),('scene_summaries','summary'),('memory_chat','result')]:
            for row in stage.execute(f'SELECT {column} FROM {table}'):
                if not isinstance(json.loads(row[0]),dict):raise ValueError('备份中的 AI 记录无效')
    finally:
        stage.close()
    return data


def _replace(db,tables):
    with db:
        for table in reversed(TABLES):db.execute('DELETE FROM '+table)
        for table,columns in TABLES.items():
            cols=columns.split()
            if not isinstance(tables[table],list):raise ValueError('备份数据表无效')
            for row in tables[table]:
                if not isinstance(row,dict) or set(row)!=set(cols) or any(type(v) not in (str,int,type(None)) for v in row.values()):raise ValueError('备份字段无效')
                insert_cols=list(cols);values=[row[c] for c in cols]
                if table=='words' and 'source' in {r[1] for r in db.execute('PRAGMA table_info(words)')}:
                    insert_cols.append('source');values.append('backup')
                db.execute('INSERT INTO '+table+'('+','.join(insert_cols)+') VALUES('+','.join('?' for _ in insert_cols)+')',values)


def restore(db,data):
    validate(data)  # Stage and validate first; the destination is untouched on error.
    _replace(db,data['tables'])


def import_legacy(db,rows):
    import core
    if not isinstance(rows,list):raise ValueError('旧版备份格式无效')
    values=[]
    for row in rows:
        word=core.normalize_word(row['word']);content=row['content']
        if not isinstance(content,dict):raise ValueError('旧版词卡无效')
        stage=row.get('stage',0);due=row.get('due',date.today().isoformat());mastery=min(1,row.get('mastery',0));date.fromisoformat(due)
        if type(stage) is not int or not 0<=stage<=7 or mastery not in (0,1):raise ValueError('旧版复习进度无效')
        learned=row.get('learned_at') or (datetime.now().isoformat() if stage>0 or mastery>0 else None)
        values.append((word,json.dumps(content,ensure_ascii=False),stage,due,mastery,learned))
    with db:
        columns='word,content,stage,due,mastery,learned_at'
        if 'source' in {r[1] for r in db.execute('PRAGMA table_info(words)')}:
            columns+=',source';values=[(*v,'backup') for v in values]
        db.executemany('INSERT OR IGNORE INTO words('+columns+') VALUES('+','.join('?' for _ in columns.split(','))+')',values)
        db.executemany('INSERT OR IGNORE INTO notebook_words VALUES(1,?)',[(v[0],) for v in values])
