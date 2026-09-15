package com.gongdi.wordcards;

import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import org.json.JSONArray;
import org.json.JSONObject;
import java.time.LocalDateTime;
import java.util.ArrayList;

/** Additive schema migration and persistence for batches, dynamic scenes and links. */
public final class DataStore {
    public final SQLiteDatabase db;
    public DataStore(SQLiteDatabase database) { db = database; migrate(); }

    private void migrate() {
        db.beginTransaction();
        try {
            db.execSQL("CREATE TABLE IF NOT EXISTS words(word TEXT PRIMARY KEY,content TEXT NOT NULL,stage INTEGER NOT NULL DEFAULT 0,due TEXT NOT NULL)");
            addColumn("words", "mastery", "INTEGER NOT NULL DEFAULT 0");
            addColumn("words", "created_batch", "INTEGER");
            db.execSQL("CREATE TABLE IF NOT EXISTS import_batches(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,status TEXT NOT NULL,source TEXT NOT NULL,raw_count INTEGER NOT NULL DEFAULT 0,confirmed_at TEXT)");
            db.execSQL("CREATE TABLE IF NOT EXISTS import_items(id INTEGER PRIMARY KEY AUTOINCREMENT,batch_id INTEGER NOT NULL,word TEXT NOT NULL,meaning TEXT NOT NULL DEFAULT '',state TEXT NOT NULL DEFAULT 'valid',error TEXT NOT NULL DEFAULT '',UNIQUE(batch_id,word))");
            db.execSQL("CREATE TABLE IF NOT EXISTS scenes(id INTEGER PRIMARY KEY AUTOINCREMENT,batch_id INTEGER NOT NULL,name TEXT NOT NULL,position INTEGER NOT NULL DEFAULT 0,user_modified INTEGER NOT NULL DEFAULT 0)");
            db.execSQL("CREATE TABLE IF NOT EXISTS scene_words(scene_id INTEGER NOT NULL,word TEXT NOT NULL,reason TEXT NOT NULL DEFAULT '',PRIMARY KEY(scene_id,word))");
            db.execSQL("CREATE TABLE IF NOT EXISTS unclassified(batch_id INTEGER NOT NULL,word TEXT NOT NULL,reason TEXT NOT NULL DEFAULT '',PRIMARY KEY(batch_id,word))");
            db.execSQL("CREATE TABLE IF NOT EXISTS word_links(id INTEGER PRIMARY KEY AUTOINCREMENT,batch_id INTEGER NOT NULL,new_word TEXT NOT NULL,old_word TEXT NOT NULL,relation TEXT NOT NULL DEFAULT '',reason TEXT NOT NULL,example TEXT NOT NULL DEFAULT '',UNIQUE(batch_id,new_word,old_word))");
            db.execSQL("CREATE TABLE IF NOT EXISTS classification_chunks(batch_id INTEGER NOT NULL,chunk_index INTEGER NOT NULL,result TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(batch_id,chunk_index))");
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_batches_status ON import_batches(status,id)");
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_scene_words_word ON scene_words(word)");
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_links_new_word ON word_links(new_word)");
            db.setVersion(3); db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    private void addColumn(String table, String column, String definition) {
        try { db.execSQL("ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition); }
        catch (Exception ignored) { }
    }

    public long createBatch(JSONObject preview, String source) throws Exception {
        db.beginTransaction();
        try {
            ContentValues batch = new ContentValues(); batch.put("created_at", LocalDateTime.now().toString()); batch.put("status", "parsed"); batch.put("source", source); batch.put("raw_count", preview.getJSONArray("items").length());
            long id = db.insertOrThrow("import_batches", null, batch);
            JSONArray items = preview.getJSONArray("items");
            for (int i=0;i<items.length();i++) { JSONObject item=items.getJSONObject(i); ContentValues v=new ContentValues();v.put("batch_id",id);v.put("word",item.getString("word"));v.put("meaning",item.optString("meaning"));v.put("state","valid");db.insertOrThrow("import_items",null,v); }
            db.setTransactionSuccessful(); return id;
        } finally { db.endTransaction(); }
    }

    public JSONArray batchItems(long batchId) throws Exception {
        JSONArray items=new JSONArray();try(Cursor c=db.rawQuery("SELECT word,meaning FROM import_items WHERE batch_id=? AND state='valid' ORDER BY id",new String[]{Long.toString(batchId)})){while(c.moveToNext())items.put(new JSONObject().put("word",c.getString(0)).put("meaning",c.getString(1)));}return items;
    }
    public JSONArray knownWords(int limit) throws Exception {
        JSONArray items=new JSONArray();try(Cursor c=db.rawQuery("SELECT word,content,mastery FROM words ORDER BY mastery DESC,stage DESC,word LIMIT ?",new String[]{Integer.toString(limit)})){while(c.moveToNext()){JSONObject content=new JSONObject(c.getString(1));items.put(new JSONObject().put("word",c.getString(0)).put("meaning",content.optString("meaning")).put("mastery",c.getInt(2)).put("scenes",scenesFor(c.getString(0))));}}return items;
    }
    public JSONArray scenesFor(String word) throws Exception { JSONArray out=new JSONArray();try(Cursor c=db.rawQuery("SELECT s.name,sw.reason FROM scenes s JOIN scene_words sw ON sw.scene_id=s.id JOIN import_batches b ON b.id=s.batch_id WHERE sw.word=? AND b.status='confirmed' ORDER BY s.id",new String[]{word})){while(c.moveToNext())out.put(new JSONObject().put("name",c.getString(0)).put("reason",c.getString(1)));}return out; }
    public JSONArray existingSceneNames(int limit)throws Exception{JSONArray out=new JSONArray();try(Cursor c=db.rawQuery("SELECT DISTINCT s.name FROM scenes s JOIN import_batches b ON b.id=s.batch_id WHERE b.status='confirmed' ORDER BY s.name LIMIT ?",new String[]{Integer.toString(limit)})){while(c.moveToNext())out.put(c.getString(0));}return out;}
    public void saveChunk(long batchId,int index,JSONObject result){ContentValues v=new ContentValues();v.put("batch_id",batchId);v.put("chunk_index",index);v.put("result",result.toString());v.put("created_at",LocalDateTime.now().toString());db.insertWithOnConflict("classification_chunks",null,v,SQLiteDatabase.CONFLICT_REPLACE);}
    public JSONObject loadChunk(long batchId,int index)throws Exception{try(Cursor c=db.rawQuery("SELECT result FROM classification_chunks WHERE batch_id=? AND chunk_index=?",new String[]{Long.toString(batchId),Integer.toString(index)})){return c.moveToFirst()?new JSONObject(c.getString(0)):null;}}
    public void clearChunks(long batchId){db.delete("classification_chunks","batch_id=?",new String[]{Long.toString(batchId)});}

    public void saveClassification(long batchId, JSONObject result) throws Exception {
        validate(result, batchItems(batchId));
        db.beginTransaction();
        try {
            db.delete("scene_words","scene_id IN (SELECT id FROM scenes WHERE batch_id=?)",new String[]{Long.toString(batchId)});db.delete("scenes","batch_id=?",new String[]{Long.toString(batchId)});db.delete("unclassified","batch_id=?",new String[]{Long.toString(batchId)});db.delete("word_links","batch_id=?",new String[]{Long.toString(batchId)});
            JSONArray cards=result.getJSONArray("cards");for(int i=0;i<cards.length();i++){JSONObject card=cards.getJSONObject(i);String word=card.getString("word");ContentValues v=new ContentValues();v.put("word",word);v.put("content",card.toString());v.put("stage",0);v.put("due",java.time.LocalDate.now().toString());v.put("created_batch",batchId);db.insertWithOnConflict("words",null,v,SQLiteDatabase.CONFLICT_IGNORE);}
            JSONArray scenes=result.getJSONArray("scenes");for(int i=0;i<scenes.length();i++){JSONObject scene=scenes.getJSONObject(i);ContentValues sv=new ContentValues();sv.put("batch_id",batchId);sv.put("name",scene.getString("name"));sv.put("position",i);long sceneId=db.insertOrThrow("scenes",null,sv);JSONArray members=scene.getJSONArray("members");for(int j=0;j<members.length();j++){JSONObject member=members.getJSONObject(j);ContentValues mv=new ContentValues();mv.put("scene_id",sceneId);mv.put("word",member.getString("word"));mv.put("reason",member.getString("reason"));db.insertOrThrow("scene_words",null,mv);}}
            JSONArray missing=result.optJSONArray("unclassified");if(missing!=null)for(int i=0;i<missing.length();i++){JSONObject item=missing.getJSONObject(i);ContentValues v=new ContentValues();v.put("batch_id",batchId);v.put("word",item.getString("word"));v.put("reason",item.optString("reason"));db.insertOrThrow("unclassified",null,v);}
            JSONArray links=result.optJSONArray("links");if(links!=null)for(int i=0;i<links.length();i++){JSONObject link=links.getJSONObject(i);ContentValues v=new ContentValues();v.put("batch_id",batchId);v.put("new_word",link.getString("new_word"));v.put("old_word",link.getString("old_word"));v.put("relation",link.optString("relation"));v.put("reason",link.getString("reason"));v.put("example",link.optString("example"));db.insertWithOnConflict("word_links",null,v,SQLiteDatabase.CONFLICT_IGNORE);}
            ContentValues state=new ContentValues();state.put("status","draft");db.update("import_batches",state,"id=?",new String[]{Long.toString(batchId)});db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    private void validate(JSONObject result, JSONArray input) throws Exception {
        java.util.HashSet<String> allowed=new java.util.HashSet<>();for(int i=0;i<input.length();i++)allowed.add(input.getJSONObject(i).getString("word"));
        JSONArray cards=result.getJSONArray("cards");java.util.HashSet<String> cardWords=new java.util.HashSet<>();for(int i=0;i<cards.length();i++){JSONObject c=cards.getJSONObject(i);String w=c.getString("word");if(!allowed.contains(w)||!cardWords.add(w))throw new Exception("AI 返回了批次外或重复的单词。");if(c.optString("meaning").trim().isEmpty())throw new Exception("AI 返回的词卡缺少释义。");}
        if(!cardWords.equals(allowed))throw new Exception("AI 没有为所有有效单词生成词卡。");
        JSONArray scenes=result.getJSONArray("scenes");int maxScenes=allowed.size()==1?1:Math.min(60,Math.max(3,(allowed.size()+3)/4+5));if(scenes.length()>maxScenes)throw new Exception("AI 返回的场景数量过多。");
        java.util.HashSet<String> covered=new java.util.HashSet<>();
        for(int i=0;i<scenes.length();i++){JSONObject s=scenes.getJSONObject(i);if(s.optString("name").trim().isEmpty())throw new Exception("场景名称为空。");JSONArray members=s.getJSONArray("members");if(members.length()==0)throw new Exception("AI 返回了空场景。");for(int j=0;j<members.length();j++){JSONObject member=members.getJSONObject(j);String word=member.getString("word");if(!allowed.contains(word)||member.optString("reason").trim().isEmpty())throw new Exception("场景成员无效。");covered.add(word);}}
        JSONArray missing=result.getJSONArray("unclassified");for(int i=0;i<missing.length();i++){JSONObject item=missing.getJSONObject(i);String word=item.getString("word");if(!allowed.contains(word)||item.optString("reason").trim().isEmpty())throw new Exception("无法分类列表无效。");covered.add(word);}
        if(!covered.equals(allowed))throw new Exception("AI 没有为所有新词给出场景或无法分类说明。");
        JSONArray links=result.getJSONArray("links");for(int i=0;i<links.length();i++){JSONObject link=links.getJSONObject(i);String newWord=link.getString("new_word"),oldWord=link.getString("old_word");if(!allowed.contains(newWord)||allowed.contains(oldWord)||link.optString("reason").trim().isEmpty()||!wordExists(oldWord))throw new Exception("AI 返回了批次外或无理由的关联。");}
    }
    public void validateClassification(JSONObject result,JSONArray input)throws Exception{validate(result,input);}

    private boolean wordExists(String word){try(Cursor c=db.rawQuery("SELECT 1 FROM words WHERE word=? LIMIT 1",new String[]{word})){return c.moveToFirst();}}

    public JSONArray batchScenes(long batchId) throws Exception {JSONArray out=new JSONArray();try(Cursor c=db.rawQuery("SELECT id,name,user_modified FROM scenes WHERE batch_id=? ORDER BY position,id",new String[]{Long.toString(batchId)})){while(c.moveToNext()){JSONObject s=new JSONObject().put("id",c.getLong(0)).put("name",c.getString(1)).put("user_modified",c.getInt(2));JSONArray members=new JSONArray();try(Cursor m=db.rawQuery("SELECT word,reason FROM scene_words WHERE scene_id=? ORDER BY word",new String[]{Long.toString(c.getLong(0))})){while(m.moveToNext())members.put(new JSONObject().put("word",m.getString(0)).put("reason",m.getString(1)));}s.put("members",members);out.put(s);}}return out;}
    public JSONArray unclassified(long batchId)throws Exception{JSONArray out=new JSONArray();try(Cursor c=db.rawQuery("SELECT word,reason FROM unclassified WHERE batch_id=? ORDER BY word",new String[]{Long.toString(batchId)})){while(c.moveToNext())out.put(new JSONObject().put("word",c.getString(0)).put("reason",c.getString(1)));}return out;}
    public JSONArray linksFor(String word)throws Exception{JSONArray out=new JSONArray();try(Cursor c=db.rawQuery("SELECT old_word,relation,reason,example FROM word_links WHERE new_word=? ORDER BY id",new String[]{word})){while(c.moveToNext())out.put(new JSONObject().put("old_word",c.getString(0)).put("relation",c.getString(1)).put("reason",c.getString(2)).put("example",c.getString(3)));}return out;}
    public long latestBatch(){try(Cursor c=db.rawQuery("SELECT id FROM import_batches WHERE status IN ('parsed','draft') ORDER BY id DESC LIMIT 1",null)){return c.moveToFirst()?c.getLong(0):-1;}}
    public String batchStatus(long id){try(Cursor c=db.rawQuery("SELECT status FROM import_batches WHERE id=?",new String[]{Long.toString(id)})){return c.moveToFirst()?c.getString(0):"";}}
    public void confirm(long id){ContentValues v=new ContentValues();v.put("status","confirmed");v.put("confirmed_at",LocalDateTime.now().toString());db.update("import_batches",v,"id=?",new String[]{Long.toString(id)});}
    public void renameScene(long sceneId,String name){ContentValues v=new ContentValues();v.put("name",name);v.put("user_modified",1);db.update("scenes",v,"id=?",new String[]{Long.toString(sceneId)});}
    public void moveWord(long from,long to,String word){db.beginTransaction();try{db.execSQL("INSERT OR REPLACE INTO scene_words(scene_id,word,reason) SELECT ?,word,reason FROM scene_words WHERE scene_id=? AND word=?",new Object[]{to,from,word});db.delete("scene_words","scene_id=? AND word=?",new String[]{Long.toString(from),word});markModified(from,to);db.setTransactionSuccessful();}finally{db.endTransaction();}}
    private void markModified(long... ids){for(long id:ids){ContentValues v=new ContentValues();v.put("user_modified",1);db.update("scenes",v,"id=?",new String[]{Long.toString(id)});}}
    public void mergeScene(long from,long to){db.beginTransaction();try{db.execSQL("INSERT OR IGNORE INTO scene_words(scene_id,word,reason) SELECT ?,word,reason FROM scene_words WHERE scene_id=?",new Object[]{to,from});db.delete("scene_words","scene_id=?",new String[]{Long.toString(from)});db.delete("scenes","id=?",new String[]{Long.toString(from)});markModified(to);db.setTransactionSuccessful();}finally{db.endTransaction();}}
    public long splitScene(long from,String name,String[] words)throws Exception{db.beginTransaction();try{long batch;try(Cursor c=db.rawQuery("SELECT batch_id FROM scenes WHERE id=?",new String[]{Long.toString(from)})){if(!c.moveToFirst())throw new Exception("场景不存在。");batch=c.getLong(0);}ContentValues s=new ContentValues();s.put("batch_id",batch);s.put("name",name);s.put("position",999);s.put("user_modified",1);long to=db.insertOrThrow("scenes",null,s);for(String word:words)moveWordWithinTransaction(from,to,Review.normalize(word));markModified(from,to);db.setTransactionSuccessful();return to;}finally{db.endTransaction();}}
    private void moveWordWithinTransaction(long from,long to,String word){db.execSQL("INSERT OR REPLACE INTO scene_words(scene_id,word,reason) SELECT ?,word,reason FROM scene_words WHERE scene_id=? AND word=?",new Object[]{to,from,word});db.delete("scene_words","scene_id=? AND word=?",new String[]{Long.toString(from),word});}
}
