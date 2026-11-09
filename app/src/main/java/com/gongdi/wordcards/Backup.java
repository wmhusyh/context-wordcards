package com.gongdi.wordcards;

import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import org.json.JSONArray;
import org.json.JSONObject;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Iterator;
import java.util.LinkedHashMap;

/** Versioned, cross-platform vocabulary snapshots. API settings and keys are excluded. */
public final class Backup {
    private static final LinkedHashMap<String,String> TABLES=new LinkedHashMap<>();
    static {
        TABLES.put("words","word content stage due mastery created_batch learned_at");
        TABLES.put("notebooks","id name position");
        TABLES.put("notebook_words","notebook_id word");
        TABLES.put("import_batches","id created_at status source raw_count confirmed_at notebook_id");
        TABLES.put("import_items","id batch_id word meaning state error");
        TABLES.put("scenes","id batch_id name position user_modified");
        TABLES.put("scene_words","scene_id word reason");
        TABLES.put("unclassified","batch_id word reason");
        TABLES.put("word_links","id batch_id new_word old_word relation reason example");
        TABLES.put("classification_chunks","batch_id chunk_index result created_at");
        TABLES.put("api_debug_responses","id batch_id chunk_index status received_at content");
        TABLES.put("review_attempts","id word question answer rating verdict feedback explanation raw_response created_at");
        TABLES.put("scene_summaries","scene_name word_fingerprint summary raw_response updated_at");
        TABLES.put("memory_chat","id word question answer result raw_response created_at");
    }
    public static JSONObject exportData(SQLiteDatabase db)throws Exception {
        JSONObject tables=new JSONObject();db.beginTransaction();
        try{for(String table:TABLES.keySet()){
            JSONArray rows=new JSONArray();String[] columns=TABLES.get(table).split(" ");
            try(Cursor c=db.query(table,columns,null,null,null,null,null)){while(c.moveToNext()){JSONObject row=new JSONObject();for(int i=0;i<columns.length;i++)row.put(columns[i],c.isNull(i)?JSONObject.NULL:c.getType(i)==Cursor.FIELD_TYPE_INTEGER?(Object)c.getLong(i):c.getString(i));rows.put(row);}}
            tables.put(table,rows);
        }db.setTransactionSuccessful();}finally{db.endTransaction();}
        return new JSONObject().put("format","context-wordcards").put("version",1).put("created_at",LocalDateTime.now().toString()).put("tables",tables);
    }
    private static void replace(SQLiteDatabase db,JSONObject tables)throws Exception{
        db.beginTransaction();try{
            for(String table:TABLES.keySet())db.delete(table,null,null);
            for(String table:TABLES.keySet()){
                JSONArray rows=tables.getJSONArray(table);String[] columns=TABLES.get(table).split(" ");
                for(int i=0;i<rows.length();i++){
                    JSONObject row=rows.getJSONObject(i);if(row.length()!=columns.length)throw new Exception("备份字段不完整。");ContentValues values=new ContentValues();
                    for(String col:columns){Object value=row.get(col);if(value==JSONObject.NULL)values.putNull(col);else if(value instanceof String)values.put(col,(String)value);else if(value instanceof Integer||value instanceof Long)values.put(col,((Number)value).longValue());else throw new Exception("备份字段类型无效。");}
                    db.insertOrThrow(table,null,values);
                }
            }db.setTransactionSuccessful();
        }finally{db.endTransaction();}
    }
    public static void validate(JSONObject data)throws Exception{
        Object version=data.opt("version");if(!"context-wordcards".equals(data.optString("format"))||!(version instanceof Integer||version instanceof Long)||((Number)version).intValue()!=1)throw new Exception("备份格式或版本不支持。");
        JSONObject tables=data.getJSONObject("tables");if(tables.length()!=TABLES.size())throw new Exception("备份数据表不完整。");for(String table:TABLES.keySet())tables.getJSONArray(table);
        SQLiteDatabase stage=SQLiteDatabase.create(null);
        try{
            new DataStore(stage);replace(stage,tables);
            try(Cursor c=stage.rawQuery("SELECT word,content,stage,due,mastery FROM words",null)){while(c.moveToNext()){
                if(!Review.normalize(c.getString(0)).equals(c.getString(0)))throw new Exception("单词格式无效。");new JSONObject(c.getString(1));
                if(c.getType(2)!=Cursor.FIELD_TYPE_INTEGER||c.getInt(2)<0||c.getInt(2)>7||c.getType(4)!=Cursor.FIELD_TYPE_INTEGER||c.getInt(4)<0||c.getInt(4)>1)throw new Exception("复习进度无效。");LocalDate.parse(c.getString(3));
            }}
            try(Cursor c=stage.rawQuery("SELECT id,name FROM notebooks",null)){boolean hasDefault=false;while(c.moveToNext()){NotebookStore.validName(c.getString(1));if(c.getLong(0)==1&&"默认单词本".equals(c.getString(1)))hasDefault=true;}if(!hasDefault)throw new Exception("缺少默认单词本。");}
            String[] checks={
                "SELECT 1 FROM notebook_words n WHERE NOT EXISTS(SELECT 1 FROM words w WHERE w.word=n.word) OR NOT EXISTS(SELECT 1 FROM notebooks b WHERE b.id=n.notebook_id)",
                "SELECT 1 FROM words w WHERE NOT EXISTS(SELECT 1 FROM notebook_words n WHERE n.word=w.word)",
                "SELECT 1 FROM import_batches b WHERE NOT EXISTS(SELECT 1 FROM notebooks n WHERE n.id=b.notebook_id)",
                "SELECT 1 FROM scenes s WHERE NOT EXISTS(SELECT 1 FROM import_batches b WHERE b.id=s.batch_id)",
                "SELECT 1 FROM scene_words sw WHERE NOT EXISTS(SELECT 1 FROM scenes s WHERE s.id=sw.scene_id) OR NOT EXISTS(SELECT 1 FROM words w WHERE w.word=sw.word)"
            };
            for(String sql:checks)try(Cursor c=stage.rawQuery(sql,null)){if(c.moveToFirst())throw new Exception("备份关联不完整。");}
            String[][] jsonFields={{"classification_chunks","result"},{"scene_summaries","summary"},{"memory_chat","result"}};
            for(String[] pair:jsonFields)try(Cursor c=stage.rawQuery("SELECT "+pair[1]+" FROM "+pair[0],null)){while(c.moveToNext())new JSONObject(c.getString(0));}
        }finally{stage.close();}
    }
    public static void restore(SQLiteDatabase db,JSONObject data)throws Exception{validate(data);replace(db,data.getJSONObject("tables"));}
    public static void importLegacy(SQLiteDatabase db,JSONArray rows)throws Exception{
        // The transaction also rolls back all previous rows if any later row is invalid.
        db.beginTransaction();try{for(int i=0;i<rows.length();i++){
            JSONObject row=rows.getJSONObject(i);String word=Review.normalize(row.getString("word"));int stage=row.optInt("stage"),mastery=Math.min(1,row.optInt("mastery"));String due=row.optString("due",LocalDate.now().toString());
            if(stage<0||stage>7||mastery<0)throw new Exception("复习进度无效。");LocalDate.parse(due);
            ContentValues v=new ContentValues();v.put("word",word);v.put("content",row.getJSONObject("content").toString());v.put("stage",stage);v.put("due",due);v.put("mastery",mastery);
            String learned=row.optString("learned_at","");if(!learned.isEmpty())v.put("learned_at",learned);else if(stage>0||mastery>0)v.put("learned_at",LocalDateTime.now().toString());
            db.insertWithOnConflict("words",null,v,SQLiteDatabase.CONFLICT_IGNORE);db.execSQL("INSERT OR IGNORE INTO notebook_words VALUES(1,?)",new Object[]{word});
        }db.setTransactionSuccessful();}finally{db.endTransaction();}
    }
}
