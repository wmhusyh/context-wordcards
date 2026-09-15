package com.gongdi.wordcards;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentValues;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** 原生 Android 界面。SQLite 保存词库，API 请求在后台线程运行。 */
public class MainActivity extends Activity {
    private final int green=Color.rgb(25,103,79), ink=Color.rgb(23,47,44), paper=Color.rgb(246,247,242), muted=Color.rgb(100,119,114);
    private SQLiteDatabase db;
    private LinearLayout body;
    private SharedPreferences prefs;
    private JSONArray profiles;
    private String active="默认", tab="add";
    private JSONObject demos;
    private boolean busy=false;
    private final HashMap<String,String> sessionKeys=new HashMap<>();
    private final ExecutorService worker=Executors.newSingleThreadExecutor();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs=getSharedPreferences("api_profiles", MODE_PRIVATE);
        try {
            db=openOrCreateDatabase("words.db", MODE_PRIVATE, null);
            db.execSQL("CREATE TABLE IF NOT EXISTS words(word TEXT PRIMARY KEY,content TEXT NOT NULL,stage INTEGER NOT NULL DEFAULT 0,due TEXT NOT NULL)");
            try(InputStream in=getAssets().open("demo.json")) { demos=new JSONObject(read(in, 100000)); }
            profiles=new JSONArray(prefs.getString("profiles", "[]"));
            if(profiles.length()==0) profiles.put(new JSONObject().put("name","默认").put("base","https://api.openai.com/v1").put("model","gpt-4.1-mini").put("responses",false));
            active=prefs.getString("active", "默认");
            if(profile(active)==null) active=profiles.getJSONObject(0).getString("name");
            home();
        } catch(Exception e) { new AlertDialog.Builder(this).setTitle("无法打开词库").setMessage("本地文件读取失败。请保留应用数据，不要卸载，联系开发者处理。").setPositiveButton("关闭",(d,w)->finish()).show(); }
    }

    private int dp(int n){return (int)(n*getResources().getDisplayMetrics().density+.5f);}
    private GradientDrawable bg(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
    private LinearLayout column(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.VERTICAL);return l;}
    private TextView text(LinearLayout parent,String value,int size,int color){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(color);t.setPadding(0,dp(6),0,dp(8));t.setTextIsSelectable(true);parent.addView(t);return t;}
    private TextView title(LinearLayout parent,String value,int size){TextView t=text(parent,value,size,ink);t.setTypeface(null,Typeface.BOLD);return t;}
    private Button button(LinearLayout parent,String label,boolean primary,Runnable action){Button b=new Button(this);b.setText(label);b.setTextSize(15);b.setAllCaps(false);b.setTextColor(primary?Color.WHITE:green);b.setBackground(bg(primary?green:Color.rgb(233,239,223),12));b.setMinHeight(dp(50));b.setPadding(dp(12),dp(10),dp(12),dp(10));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,dp(7),0,dp(7));parent.addView(b,lp);b.setOnClickListener(v->action.run());return b;}
    private EditText input(LinearLayout parent,String label,String value,boolean multiline){text(parent,label,14,muted);EditText e=new EditText(this);e.setTextSize(16);e.setTextColor(ink);e.setText(value);e.setSingleLine(!multiline);e.setInputType(InputType.TYPE_CLASS_TEXT|(multiline?InputType.TYPE_TEXT_FLAG_MULTI_LINE:InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS));e.setPadding(dp(12),dp(12),dp(12),dp(12));e.setBackground(bg(Color.rgb(242,245,239),10));parent.addView(e,new LinearLayout.LayoutParams(-1,-2));return e;}
    private LinearLayout card(){LinearLayout l=column();l.setPadding(dp(20),dp(18),dp(20),dp(18));l.setBackground(bg(Color.WHITE,20));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,dp(14),0,dp(8));body.addView(l,lp);return l;}
    private void message(String value){new AlertDialog.Builder(this).setTitle("工地词卡").setMessage(value).setPositiveButton("知道了",null).show();}
    private void toast(String value){Toast.makeText(this,value,Toast.LENGTH_LONG).show();}
    private String today(){return LocalDate.now().toString();}

    private void page(String section,String heading,String sub){
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
        tab=section;
        LinearLayout root=column();root.setBackgroundColor(paper);
        root.setOnApplyWindowInsetsListener((v,insets)->{v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        LinearLayout top=new LinearLayout(this);top.setGravity(Gravity.CENTER_VERTICAL);top.setPadding(dp(20),dp(6),dp(20),0);
        TextView logo=new TextView(this);logo.setText("▣ 工地词卡");logo.setTextColor(green);logo.setTypeface(null,Typeface.BOLD);logo.setTextSize(19);top.addView(logo,new LinearLayout.LayoutParams(0,dp(50),1));logo.setGravity(Gravity.CENTER_VERTICAL);
        Button settings=new Button(this);settings.setText("API 设置");settings.setTextColor(green);settings.setAllCaps(false);top.addView(settings);settings.setOnClickListener(v->settings(active));root.addView(top);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);body=column();body.setPadding(dp(20),dp(12),dp(20),dp(24));scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        title(body,heading,29);text(body,sub,14,muted);
        LinearLayout nav=new LinearLayout(this);nav.setPadding(dp(10),dp(4),dp(10),dp(4));
        String[] labels={"＋ 添加","▤ 单词本","✓ 复习"};String[] tabs={"add","words","review"};
        for(int i=0;i<3;i++){final int which=i;Button b=new Button(this);b.setText(labels[i]);b.setAllCaps(false);b.setTextSize(14);b.setTextColor(section.equals(tabs[i])?Color.WHITE:green);b.setBackground(bg(section.equals(tabs[i])?green:paper,12));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(52),1);lp.setMargins(dp(3),0,dp(3),0);nav.addView(b,lp);b.setOnClickListener(v->{if(which==0)home();else if(which==1)library();else review();});}
        root.addView(nav);setContentView(root);root.requestApplyInsets();
    }

    private ArrayList<JSONObject> rows(){ArrayList<JSONObject> list=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT word,content,stage,due FROM words ORDER BY word",null)){while(c.moveToNext())list.add(new JSONObject().put("word",c.getString(0)).put("content",new JSONObject(c.getString(1))).put("stage",c.getInt(2)).put("due",c.getString(3)));}catch(Exception e){message("词库读取失败，请保留应用数据。");}return list;}
    private JSONObject find(String word){for(JSONObject r:rows())if(r.optString("word").equals(word))return r;return null;}
    private int dueCount(){int n=0;for(JSONObject r:rows())if(r.optString("due").compareTo(today())<=0)n++;return n;}
    private boolean save(String word,JSONObject content){ContentValues v=new ContentValues();v.put("word",word);v.put("content",content.toString());v.put("stage",0);v.put("due",today());try{db.insertOrThrow("words",null,v);return true;}catch(Exception e){message("未能保存。请检查手机可用空间，或确认单词是否已存在。");return false;}}

    private void home(){
        page("add","从一个单词开始。","本机保存 · 离线可复习 · 无需电脑");
        text(body,rows().size()+" 个单词   /   今天待复习 "+dueCount()+" 个",17,green);
        LinearLayout c=card();title(c,"今天想学什么？",21);EditText word=input(c,"英文单词或短语","",false);word.setHint("例如 scaffold");
        text(c,"当前 API："+active+(busy?" · 正在生成…":""),13,muted);
        button(c,"用当前 API 生成",true,()->{try{generate(Review.normalize(word.getText().toString()));}catch(Exception e){message(e.getMessage());}});
        button(c,"手动添加，不用联网",false,()->manual(word.getText().toString()));
        LinearLayout demo=card();title(demo,"先试三个施工词汇",20);text(demo,"预置学习卡片，完全离线。",14,muted);
        for(String w:new String[]{"scaffold","concrete","helmet"})button(demo,w,false,()->{try{if(find(w)==null&&!save(w,demos.getJSONObject(w)))return;detail(w,false);}catch(Exception e){message("无法读取示例。");}});
        button(body,"开始今日复习 →",true,()->review());
    }

    private void library(){
        page("words","我的单词本","所有内容都在手机里，关闭电脑也能用。");
        EditText search=input(body,"搜索英文或中文意思","",false);LinearLayout list=column();body.addView(list);
        Runnable render=()->{list.removeAllViews();String q=search.getText().toString().toLowerCase(java.util.Locale.ROOT).trim();int count=0;
            for(JSONObject r:rows()){String w=r.optString("word"), meaning=r.optJSONObject("content").optString("meaning");if(!w.contains(q)&&!meaning.contains(q))continue;count++;button(list,w+"  ·  "+meaning+"\n"+(r.optString("due").compareTo(today())<=0?"今天复习":"下次："+r.optString("due")),false,()->detail(w,false));}
            if(count==0)text(list,q.isEmpty()?"还没有单词，先添加一个吧。":"没有找到匹配的单词。",16,muted);
        };render.run();search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){render.run();}public void afterTextChanged(Editable e){}});
        button(body,"导出词库备份",false,()->{Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("application/json");i.putExtra(Intent.EXTRA_TITLE,"工地词卡-"+today()+".json");startActivityForResult(i,10);});
        button(body,"从备份导入",false,()->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("application/json");startActivityForResult(i,11);});
    }

    private void manual(String initial){
        page("add","手动添加","只需填英文和意思，就能开始离线复习。");LinearLayout c=card();EditText word=input(c,"英文单词或短语",initial,false);EditText meaning=input(c,"中文意思（必填）","",true);EditText example=input(c,"英文例句（选填）","",true);EditText translation=input(c,"例句翻译（选填）","",true);
        button(c,"保存到手机",true,()->{try{String w=Review.normalize(word.getText().toString()),m=meaning.getText().toString().trim();if(m.isEmpty()){message("请填写中文意思。");return;}if(find(w)!=null){message("这个词已经存在，可在单词本查看。");return;}JSONObject content=new JSONObject();for(String f:ApiClient.FIELDS)content.put(f,"");content.put("meaning",m).put("example",example.getText().toString().trim()).put("translation",translation.getText().toString().trim()).put("quiz","“"+m+"”用英语怎么说？").put("answer",w);if(save(w,content))detail(w,false);}catch(Exception e){message(e.getMessage());}});
    }

    private void detail(String word,boolean reviewing){
        JSONObject row=find(word);if(row==null){library();return;}
        page(reviewing?"review":"words",reviewing?"先回忆，再翻开":"单词卡片",reviewing?"今天还有 "+dueCount()+" 个单词":"下次复习："+row.optString("due"));
        LinearLayout c=card();title(c,word,34);
        if(reviewing){text(c,"它是什么意思？试着用它说一句英语。",16,muted);button(c,"显示答案",true,()->{showDetails(word,row,true);});}
        else showDetails(word,row,false);
    }

    private void showDetails(String word,JSONObject row,boolean reviewing){
        page(reviewing?"review":"words",word,reviewing?"想一想自己刚才的答案，再选择记忆程度。":"已保存在手机，可离线查看。");
        JSONObject content=row.optJSONObject("content");LinearLayout c=card();title(c,content.optString("meaning"),24);
        String[] fields={"part_of_speech","explanation","example","translation","memory","quiz"};String[] labels={"词性","简单解释","例句","翻译","记忆提示","小测试"};
        for(int i=0;i<fields.length;i++){String s=content.optString(fields[i]);if(!s.isEmpty()){text(c,labels[i],13,green);text(c,s,17,ink);}}
        if(!content.optString("answer").isEmpty())button(c,"查看小测试参考答案",false,()->message(content.optString("answer")));
        if(reviewing){
            for(int i=1;i<=3;i++){final int rating=i;String label=i==1?"认识 · 拉长复习间隔":i==2?"有点模糊 · 明天再看":"不认识 · 明天重新开始";button(body,label,i==1,()->rate(word,row,rating));}
        }else{
            button(body,"去今天复习",true,()->review());
            button(body,"删除这个单词",false,()->new AlertDialog.Builder(this).setTitle("删除 "+word+"？").setMessage("词卡和复习进度将一起删除。").setNegativeButton("取消",null).setPositiveButton("删除",(d,w)->{try{db.delete("words","word=?",new String[]{word});library();}catch(Exception e){message("删除失败，请重试。");}}).show());
        }
    }

    private void review(){for(JSONObject row:rows())if(row.optString("due").compareTo(today())<=0){detail(row.optString("word"),true);return;}page("review",rows().isEmpty()?"先收藏一个单词吧":"今天复习完成了","不用一次记住所有，明天再见一面。");button(body,"继续学新词",true,()->home());}
    private void rate(String word,JSONObject row,int rating){try{String[] next=Review.next(row.getInt("stage"),rating,LocalDate.now());ContentValues v=new ContentValues();v.put("stage",Integer.parseInt(next[0]));v.put("due",next[1]);int count=db.update("words",v,"word=? AND due=? AND stage=?",new String[]{word,row.getString("due"),row.getString("stage")});toast(count==1?"已保存，下次复习："+next[1]:"进度已更新，请继续复习。");review();}catch(Exception e){message("评分未保存，请重试。");}}

    private JSONObject profile(String name){for(int i=0;i<profiles.length();i++){JSONObject p=profiles.optJSONObject(i);if(p!=null&&name.equals(p.optString("name")))return p;}return null;}
    private void persistProfiles(){prefs.edit().putString("profiles",profiles.toString()).putString("active",active).apply();}
    private void settings(String selected){
        page("add","自由切换 API","支持 OpenAI 兼容接口；离线功能不需要配置。");
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE);
        LinearLayout pick=card();title(pick,"已保存的配置",20);
        for(int i=0;i<profiles.length();i++){String n=profiles.optJSONObject(i).optString("name");button(pick,(n.equals(active)?"✓ ":"")+n,false,()->settings(n));}
        button(pick,"＋ 新建配置",false,()->settings(""));
        JSONObject p=profile(selected);LinearLayout c=card();
        EditText name=input(c,"配置名称",p==null?"":selected,false);
        EditText base=input(c,"Base URL 或完整接口地址",p==null?"https://":p.optString("base"),false);
        EditText model=input(c,"模型名称",p==null?"":p.optString("model"),false);
        text(c,"接口格式",14,muted);Spinner protocol=new Spinner(this);protocol.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"Chat Completions（兼容接口常用）","Responses"}));protocol.setSelection(p!=null&&p.optBoolean("responses")?1:0);c.addView(protocol);
        EditText key=input(c,"API Key（仅本次运行，重开需重新输入）",sessionKeys.containsKey(selected)?sessionKeys.get(selected):"",false);key.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);key.setSaveEnabled(false);key.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        text(c,"密钥和待学单词会发送给你选定的服务商。地址与模型会保存，密钥不会保存到磁盘。",13,muted);
        button(c,"保存并切换到此配置",true,()->{try{
            String n=name.getText().toString().trim(),b=base.getText().toString().trim(),m=model.getText().toString().trim();boolean responses=protocol.getSelectedItemPosition()==1;
            if(n.isEmpty()||n.length()>40||m.isEmpty()||m.length()>200){message("请填写配置名称（最多 40 字）和模型名称。");return;}
            if(!n.equals(selected)&&profile(n)!=null){message("配置名称已存在，请换一个名称。");return;}
            String endpoint=ApiClient.endpoint(b,responses);String k=key.getText().toString().trim();if(k.contains("\n")||k.contains("\r")){message("密钥不能包含换行。");return;}
            JSONObject updated=new JSONObject().put("name",n).put("base",b).put("model",m).put("responses",responses);
            JSONArray next=new JSONArray();for(int i=0;i<profiles.length();i++)if(!selected.equals(profiles.getJSONObject(i).optString("name")))next.put(profiles.getJSONObject(i));next.put(updated);
            profiles=next;active=n;sessionKeys.remove(selected);sessionKeys.put(n,k);persistProfiles();toast("已切换到 "+n);home();
        }catch(Exception e){message(e.getMessage());}});
        if(p!=null&&profiles.length()>1)button(c,"删除此配置",false,()->new AlertDialog.Builder(this).setTitle("删除配置？").setMessage("不会删除单词本。").setNegativeButton("取消",null).setPositiveButton("删除",(d,w)->{JSONArray next=new JSONArray();for(int i=0;i<profiles.length();i++)if(!selected.equals(profiles.optJSONObject(i).optString("name")))next.put(profiles.optJSONObject(i));profiles=next;sessionKeys.remove(selected);if(active.equals(selected))active=profiles.optJSONObject(0).optString("name");persistProfiles();settings(active);}).show());
        text(body,"例如 Base URL 填 https://api.openai.com/v1，程序按所选格式补上 /chat/completions 或 /responses。也可以直接填完整地址。仅支持 HTTPS + Bearer Key 的兼容接口，不支持服务商专有认证。",13,muted);
    }

    private void generate(String word){
        if(busy){message("已有一个词正在生成，请稍候。");return;}
        if(find(word)!=null){detail(word,false);return;}
        JSONObject p=profile(active);if(p==null){settings(active);return;}
        final String base=p.optString("base"),model=p.optString("model"),name=active,key=sessionKeys.containsKey(active)?sessionKeys.get(active):"";final boolean responses=p.optBoolean("responses");
        if(key.isEmpty()){message("请先在 API 设置中填写此配置的密钥。无需密钥的自建接口暂不支持。");settings(active);return;}
        new AlertDialog.Builder(this).setTitle("生成 "+word+"？").setMessage("使用「"+name+"」的 "+model+" 模型。此操作会联网，服务商可能计费。").setNegativeButton("取消",null).setPositiveButton("生成",(d,w)->{
            if(busy)return;busy=true;home();toast("正在生成，可继续浏览已保存的词。");
            worker.execute(()->{try{JSONObject content=ApiClient.generate(word,base,model,key,responses);runOnUiThread(()->{busy=false;if(isFinishing()||isDestroyed())return;if(find(word)!=null){toast("这个词已存在，保留原内容。");return;}if(save(word,content)){toast(word+" 已保存");detail(word,false);}});}catch(Exception e){String err=e instanceof java.net.SocketTimeoutException?"连接超时，未保存，请检查网络后重试。":e instanceof java.io.IOException?"无法连接服务商，请检查地址、网络和证书。":e instanceof org.json.JSONException?"服务商返回格式不兼容或内容不是完整 JSON，未保存。":e.getMessage();runOnUiThread(()->{busy=false;if(!isFinishing()&&!isDestroyed()){home();message(err==null?"生成失败，未保存。":err);}});}});
        }).show();
    }

    private static String read(InputStream in,int limit)throws Exception{ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){out.write(b,0,n);if(out.size()>limit)throw new Exception("文件过大。");}return new String(out.toByteArray(),StandardCharsets.UTF_8);}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null||data.getData()==null)return;
        try{
            if(request==10){JSONArray list=new JSONArray();for(JSONObject r:rows())list.put(r);try(OutputStream out=getContentResolver().openOutputStream(data.getData(),"wt")){if(out==null)throw new Exception();out.write(list.toString(2).getBytes(StandardCharsets.UTF_8));}toast("词库已导出，不含 API 密钥或设置。");}
            if(request==11){JSONArray list;try(InputStream in=getContentResolver().openInputStream(data.getData())){if(in==null)throw new Exception();list=new JSONArray(read(in,5*1024*1024));}if(list.length()>10000)throw new Exception("最多导入一万个单词。");
                ArrayList<ContentValues> values=new ArrayList<>();for(int i=0;i<list.length();i++){JSONObject row=list.getJSONObject(i);String w=Review.normalize(row.getString("word"));JSONObject c=row.getJSONObject("content");if(c.optString("meaning").trim().isEmpty())throw new Exception("备份中存在缺少意思的单词。");for(String f:ApiClient.FIELDS)if(c.has(f)&&!(c.get(f) instanceof String))throw new Exception("卡片字段类型错误。");int stage=row.getInt("stage");if(stage<0||stage>4)throw new Exception("复习阶段无效。");String due=LocalDate.parse(row.getString("due")).toString();ContentValues v=new ContentValues();v.put("word",w);v.put("content",c.toString());v.put("stage",stage);v.put("due",due);values.add(v);}
                new AlertDialog.Builder(this).setTitle("导入 "+values.size()+" 个单词？").setMessage("已有同名单词会保留，不覆盖现有复习进度。").setNegativeButton("取消",null).setPositiveButton("导入",(d,w)->{int count=0;db.beginTransaction();try{for(ContentValues v:values)if(db.insertWithOnConflict("words",null,v,SQLiteDatabase.CONFLICT_IGNORE)!=-1)count++;db.setTransactionSuccessful();toast("导入 "+count+" 个新词。");}catch(Exception e){message("导入失败，未保存本次导入内容。");}finally{db.endTransaction();}library();}).show();
            }
        }catch(Exception e){message("操作失败：文件不可读、格式不正确或没有足够空间。原词库未被覆盖。");}
    }
    @Override public void onBackPressed(){if(!"add".equals(tab))home();else super.onBackPressed();}
    @Override protected void onDestroy(){worker.shutdownNow();sessionKeys.clear();if(db!=null)db.close();super.onDestroy();}
}
