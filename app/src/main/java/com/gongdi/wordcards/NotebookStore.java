package com.gongdi.wordcards;

import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import org.json.JSONArray;
import org.json.JSONObject;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Locale;

/** Notebooks organize references to words; schedules always stay on words. */
public final class NotebookStore {
    private final SQLiteDatabase db;
    public NotebookStore(SQLiteDatabase db) { this.db=db; }
    public void migrate() {
        boolean first;
        try(Cursor c=db.rawQuery("SELECT 1 FROM sqlite_master WHERE name='notebooks'",null)){first=!c.moveToFirst();}
        db.execSQL("CREATE TABLE IF NOT EXISTS notebooks(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,position INTEGER NOT NULL DEFAULT 0)");
        db.execSQL("CREATE TABLE IF NOT EXISTS notebook_words(notebook_id INTEGER NOT NULL,word TEXT NOT NULL,PRIMARY KEY(notebook_id,word))");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_notebook_word ON notebook_words(word)");
        boolean hasColumn=false;
        try(Cursor c=db.rawQuery("PRAGMA table_info(import_batches)",null)){while(c.moveToNext())if("notebook_id".equals(c.getString(1)))hasColumn=true;}
        if(!hasColumn)db.execSQL("ALTER TABLE import_batches ADD COLUMN notebook_id INTEGER NOT NULL DEFAULT 1");
        db.execSQL("INSERT OR IGNORE INTO notebooks(id,name,position) VALUES(1,'默认单词本',0)");
        if(first)db.execSQL("INSERT OR IGNORE INTO notebook_words SELECT 1,word FROM words");
    }
    public static String validName(String name) {
        name=name.trim();
        if(name.isEmpty()||name.length()>40||name.equals("全部单词"))throw new IllegalArgumentException("名称需为 1–40 个字符，不能使用“全部单词”。");
        return name;
    }
    public boolean exists(long id){try(Cursor c=db.rawQuery("SELECT 1 FROM notebooks WHERE id=?",new String[]{""+id})){return c.moveToFirst();}}
    public long create(String name){ContentValues v=new ContentValues();v.put("name",validName(name));try(Cursor c=db.rawQuery("SELECT COALESCE(MAX(position),0)+1 FROM notebooks",null)){c.moveToFirst();v.put("position",c.getInt(0));}return db.insertOrThrow("notebooks",null,v);}
    public void rename(long id,String name){if(id==1)throw new IllegalArgumentException("默认单词本保留固定名称。");ContentValues v=new ContentValues();v.put("name",validName(name));db.update("notebooks",v,"id=?",new String[]{""+id});}
    public String name(long id){try(Cursor c=db.rawQuery("SELECT name FROM notebooks WHERE id=?",new String[]{""+id})){return c.moveToFirst()?c.getString(0):"全部单词";}}
    public void add(long id,ArrayList<String> words){
        if(!exists(id))throw new IllegalArgumentException("单词本不存在，请重新选择。");
        db.beginTransaction();try{for(String word:words){try(Cursor c=db.rawQuery("SELECT 1 FROM words WHERE word=?",new String[]{word})){if(!c.moveToFirst())throw new IllegalArgumentException("单词不存在："+word);}db.execSQL("INSERT OR IGNORE INTO notebook_words VALUES(?,?)",new Object[]{id,word});}db.setTransactionSuccessful();}finally{db.endTransaction();}
    }
    private void keepReachable(){db.execSQL("INSERT OR IGNORE INTO notebook_words SELECT 1,word FROM words w WHERE NOT EXISTS(SELECT 1 FROM notebook_words n WHERE n.word=w.word)");}
    public void remove(long id,ArrayList<String> words){db.beginTransaction();try{for(String word:words)db.delete("notebook_words","notebook_id=? AND word=?",new String[]{""+id,word});keepReachable();db.setTransactionSuccessful();}finally{db.endTransaction();}}
    public void delete(long id){if(id==1)throw new IllegalArgumentException("默认单词本不能删除。");db.beginTransaction();try{db.delete("notebook_words","notebook_id=?",new String[]{""+id});db.execSQL("UPDATE import_batches SET notebook_id=1 WHERE notebook_id=?",new Object[]{id});db.delete("notebooks","id=?",new String[]{""+id});keepReachable();db.setTransactionSuccessful();}finally{db.endTransaction();}}
    public void move(long id,int direction)throws Exception{
        ArrayList<Long> ids=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT id FROM notebooks ORDER BY position,id",null)){while(c.moveToNext())ids.add(c.getLong(0));}
        int index=ids.indexOf(id),other=index+direction;if(index<0||other<0||other>=ids.size())return;
        java.util.Collections.swap(ids,index,other);db.beginTransaction();try{for(int i=0;i<ids.size();i++)db.execSQL("UPDATE notebooks SET position=? WHERE id=?",new Object[]{i,ids.get(i)});db.setTransactionSuccessful();}finally{db.endTransaction();}
    }
    public JSONArray books()throws Exception{
        JSONArray out=new JSONArray();String sql="SELECT n.id,n.name,COUNT(w.word),COALESCE(SUM(CASE WHEN w.word IS NOT NULL AND w.learned_at IS NULL THEN 1 ELSE 0 END),0),COALESCE(SUM(CASE WHEN w.learned_at IS NOT NULL AND w.due<=? THEN 1 ELSE 0 END),0) FROM notebooks n LEFT JOIN notebook_words nw ON nw.notebook_id=n.id LEFT JOIN words w ON w.word=nw.word GROUP BY n.id ORDER BY n.position,n.id";
        try(Cursor c=db.rawQuery(sql,new String[]{LocalDate.now().toString()})){while(c.moveToNext())out.put(new JSONObject().put("id",c.getLong(0)).put("name",c.getString(1)).put("total",c.getInt(2)).put("unlearned",c.getInt(3)).put("due",c.getInt(4)));}return out;
    }
    public ArrayList<JSONObject> words(long book,String query,boolean dueOnly)throws Exception{
        ArrayList<JSONObject> out=new ArrayList<>();ArrayList<String> args=new ArrayList<>();String sql="SELECT w.word,w.content,w.stage,w.due,w.mastery,w.learned_at,(SELECT GROUP_CONCAT(s.name,' ') FROM scenes s JOIN scene_words sw ON sw.scene_id=s.id WHERE sw.word=w.word) FROM words w WHERE 1=1";
        if(book>0){sql+=" AND EXISTS(SELECT 1 FROM notebook_words nw WHERE nw.word=w.word AND nw.notebook_id=?)";args.add(""+book);}
        if(dueOnly){sql+=" AND w.learned_at IS NOT NULL AND w.due<=?";args.add(LocalDate.now().toString());}
        sql+=" ORDER BY w.word";String q=query.trim().toLowerCase(Locale.ROOT);
        try(Cursor c=db.rawQuery(sql,args.toArray(new String[0]))){while(c.moveToNext()){JSONObject content=new JSONObject(c.getString(1));String hay=c.getString(0)+" "+content.optString("meaning")+" "+(c.isNull(6)?"":c.getString(6));if(!q.isEmpty()&&!hay.toLowerCase(Locale.ROOT).contains(q))continue;out.add(new JSONObject().put("word",c.getString(0)).put("content",content).put("stage",c.getInt(2)).put("due",c.getString(3)).put("mastery",c.getInt(4)).put("learned_at",c.isNull(5)?"":c.getString(5)));}}return out;
    }
}
