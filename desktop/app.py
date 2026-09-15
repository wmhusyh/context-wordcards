"""Tkinter desktop app. Run: python desktop/app.py"""
from __future__ import annotations
import json, sqlite3, sys, threading
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

sys.path.insert(0,str(Path(__file__).resolve().parent))
import core

ROOT=Path(__file__).resolve().parent

class App(tk.Tk):
    def __init__(self,db_path=None):
        super().__init__();self.title("情境词卡");self.geometry("980x700");self.minsize(760,560)
        legacy=ROOT.parent/"outputs"/"words.db";default_db=legacy if legacy.exists() else ROOT/"context_words.db"
        self.db=core.connect(Path(db_path or default_db));self.preview=None;self.batch=None;self.busy=False
        self.keys_path=ROOT/".api_keys.json";self.keys=self._load_keys()
        style=ttk.Style(self);style.configure("Title.TLabel",font=("Microsoft YaHei UI",22,"bold"));style.configure("Sub.TLabel",foreground="#657470")
        self.tabs=ttk.Notebook(self);self.tabs.pack(fill="both",expand=True,padx=14,pady=14)
        self.import_tab=ttk.Frame(self.tabs);self.scene_tab=ttk.Frame(self.tabs);self.word_tab=ttk.Frame(self.tabs);self.review_tab=ttk.Frame(self.tabs);self.api_tab=ttk.Frame(self.tabs)
        for frame,name in [(self.import_tab,"批量导入"),(self.scene_tab,"场景预览"),(self.word_tab,"单词本"),(self.review_tab,"今天复习"),(self.api_tab,"API 设置")]:self.tabs.add(frame,text=name)
        self._build_import();self._build_scenes();self._build_words();self._build_review();self._build_api();self.refresh_all();self.protocol("WM_DELETE_WINDOW",self.close)

    def _load_keys(self):
        try:return {k:core.unprotect(v) for k,v in json.loads(self.keys_path.read_text(encoding="utf-8")).items()}
        except Exception:return {}
    def _save_keys(self):
        data={k:core.protect(v) for k,v in self.keys.items() if v};self.keys_path.write_text(json.dumps(data),encoding="utf-8")
    def label(self,parent,text,style=None):return ttk.Label(parent,text=text,style=style or "TLabel")
    def active_profile(self):return self.db.execute("SELECT * FROM api_profiles WHERE is_active=1").fetchone()
    def async_run(self,work,done):
        if self.busy:return messagebox.showinfo("请稍候","已有 AI 请求正在执行")
        self.busy=True
        def task():
            try: result=work();self.after(0,lambda:(setattr(self,"busy",False),done(result)))
            except Exception as exc:
                def failed(e=exc):
                    self.busy=False
                    if str(e).startswith("HTTP 401"):
                        profile=self.active_profile()
                        if profile:self.keys.pop(profile["name"],None);self._save_keys();self.tabs.select(self.api_tab)
                    messagebox.showerror("操作失败",str(e))
                self.after(0,failed)
        threading.Thread(target=task,daemon=True).start()

    def _build_import(self):
        top=ttk.Frame(self.import_tab,padding=16);top.pack(fill="both",expand=True);self.label(top,"批量导入单词","Title.TLabel").pack(anchor="w");self.label(top,"无需选择场景。粘贴或选择 CSV 后先预览，再由 AI 根据整批关系自动聚类。","Sub.TLabel").pack(anchor="w",pady=(2,12))
        self.raw=tk.Text(top,height=13,font=("Consolas",11),wrap="word");self.raw.pack(fill="both",expand=True);self.raw.insert("1.0","boarding pass: 登机牌\ncheck in\npassport")
        actions=ttk.Frame(top);actions.pack(fill="x",pady=10);ttk.Button(actions,text="预览粘贴内容",command=self.preview_paste).pack(side="left");ttk.Button(actions,text="选择 CSV",command=self.choose_csv).pack(side="left",padx=8);ttk.Button(actions,text="继续未完成批次",command=self.resume_latest).pack(side="left");ttk.Button(actions,text="查看 AI 调试返回",command=self.show_debug_responses).pack(side="left",padx=8)
        self.import_summary=tk.StringVar(value="等待导入");self.label(top,"支持每行一个单词、word: 释义，以及 CSV 的前两列。", "Sub.TLabel").pack(anchor="w");summary=self.label(top,"");summary.configure(textvariable=self.import_summary);summary.pack(anchor="w")

    def preview_paste(self):self.show_preview(core.parse_import(self.raw.get("1.0","end")),"paste")
    def choose_csv(self):
        path=filedialog.askopenfilename(filetypes=[("CSV","*.csv"),("文本","*.txt"),("所有文件","*.*")]);
        if path:self.show_preview(core.parse_import(Path(path).read_text(encoding="utf-8-sig"),True),"csv")
    def show_preview(self,result,source):
        existing={r[0] for r in self.db.execute("SELECT word FROM words")};kept=[x for x in result["items"] if x["word"] not in existing];old=[x for x in result["items"] if x["word"] in existing];result["items"]=kept;result["existing"]=old;self.preview=(result,source)
        win=tk.Toplevel(self);win.title("导入预览");win.geometry("720x520");self.label(win,f"可导入 {len(kept)} 个；已有 {len(old)} 个；本批重复 {len(result['duplicates'])} 个；格式问题 {len(result['errors'])} 个；空行 {result['empty_lines']}","Title.TLabel").pack(anchor="w",padx=16,pady=12)
        tree=ttk.Treeview(win,columns=("meaning","state"),show="tree headings");tree.heading("#0",text="单词 / 原文");tree.heading("meaning",text="释义");tree.heading("state",text="状态");tree.pack(fill="both",expand=True,padx=16)
        for x in kept:tree.insert("", "end",text=x["word"],values=(x["meaning"],"可导入"))
        for x in old:tree.insert("", "end",text=x["word"],values=(x["meaning"],"已存在，跳过"))
        for x in result["errors"]:tree.insert("", "end",text=x["raw"],values=(x["message"],f"第 {x['line']} 行错误"))
        bar=ttk.Frame(win);bar.pack(fill="x",padx=16,pady=12);ttk.Button(bar,text="返回修改",command=win.destroy).pack(side="right");ttk.Button(bar,text="确认并让 AI 分类",command=lambda:(win.destroy(),self.start_import())).pack(side="right",padx=8)
    def start_import(self):
        if not self.preview or not self.preview[0]["items"]:return messagebox.showwarning("没有新词","没有可导入的新单词")
        self.batch=core.create_batch(self.db,self.preview[0],self.preview[1]);self.classify(self.batch)
    def resume_latest(self):
        row=self.db.execute("SELECT id,status FROM import_batches WHERE status IN ('parsed','draft') ORDER BY id DESC LIMIT 1").fetchone()
        if not row:return messagebox.showinfo("没有草稿","没有未完成批次")
        self.batch=row["id"]
        if row["status"]=="parsed":self.classify(self.batch)
        else:self.tabs.select(self.scene_tab);self.refresh_scenes()
    def classify(self,batch,replace=False):
        p=self.active_profile();key=self.keys.get(p["name"],"") if p else ""
        if not p or not key:self.tabs.select(self.api_tab);return messagebox.showinfo("需要 API 密钥","请先填写并验证 API 密钥。导入批次已经保存。")
        if replace and not messagebox.askyesno("重新分类","这会替换本批的分类和人工调整，是否继续？"):return
        if replace:core.clear_chunks(self.db,batch)
        items=core.batch_items(self.db,batch);known=core.known_words(self.db,excluded={x["word"] for x in items});existing=core.existing_scene_names(self.db)
        self.import_summary.set("AI 正在分组分析单词…")
        def work():
            total=core.empty_classification();size=30;groups=(len(items)+size-1)//size
            for index in range(groups):
                self.after(0,lambda n=index+1:self.import_summary.set(f"正在分析第 {n} / {groups} 组"))
                chunk=items[index*size:(index+1)*size]
                part=core.load_chunk(self.db,batch,index)
                if part is None:
                    raw=""
                    try:
                        raw=core.request_batch_raw(p["base"],p["model"],p["protocol"],key,chunk,known,existing);part=core.parse_batch_response(raw,p["protocol"]);dropped=core.sanitize_links(self.db,part,chunk,items);core.validate_result(part,chunk,known);core.save_debug_response(self.db,batch,index,f"有效，已忽略 {dropped} 条无效关联" if dropped else "有效",raw.replace(key,"***"));core.save_chunk(self.db,batch,index,part)
                    except Exception as exc:
                        response=getattr(exc,"response_body","");content=(raw+"\n\n[本地解析或校验]\n"+str(exc)) if raw else ((response+"\n\n[HTTP 错误]\n"+str(exc)) if response else str(exc));core.save_debug_response(self.db,batch,index,"失败",content.replace(key,"***"));raise
                else:
                    dropped=core.sanitize_links(self.db,part,chunk,items);core.validate_result(part,chunk,known)
                    if dropped:core.save_chunk(self.db,batch,index,part);core.save_debug_response(self.db,batch,index,f"缓存修复，已忽略 {dropped} 条无效关联",json.dumps(part,ensure_ascii=False,indent=2))
                core.merge_classification(total,part)
                for scene in part["scenes"]:
                    if scene["name"] not in existing:existing.append(scene["name"])
            return total
        self.async_run(work,lambda result:self._classified(batch,result))

    def show_debug_responses(self):
        batch=self.batch
        if not batch:
            row=self.db.execute("SELECT id FROM import_batches ORDER BY id DESC LIMIT 1").fetchone();batch=row["id"] if row else None
        if not batch:return messagebox.showinfo("没有记录","还没有导入批次。")
        logs=core.debug_responses(self.db,batch);win=tk.Toplevel(self);win.title("AI 调试返回");win.geometry("860x640")
        self.label(win,"按时间保存接口原始返回和本地校验结果；不保存请求内容或 API Key。","Sub.TLabel").pack(anchor="w",padx=14,pady=10)
        output=tk.Text(win,font=("Consolas",10),wrap="word");output.pack(fill="both",expand=True,padx=14,pady=(0,14))
        if not logs:output.insert("end","这个批次还没有可查看的返回记录。")
        for log in logs:output.insert("end",f"第 {log['chunk_index']+1} 组 · {log['status']} · {log['received_at']}\n{'='*72}\n{log['content']}\n\n")
        output.configure(state="disabled")
    def _classified(self,batch,result):core.save_classification(self.db,batch,result);core.clear_chunks(self.db,batch);self.batch=batch;self.import_summary.set("分类草稿已保存");self.tabs.select(self.scene_tab);self.refresh_all()

    def _build_scenes(self):
        frame=ttk.Frame(self.scene_tab,padding=16);frame.pack(fill="both",expand=True);self.label(frame,"场景分类预览","Title.TLabel").pack(anchor="w");self.scene_status=tk.StringVar();self.label(frame,"","Sub.TLabel").configure(textvariable=self.scene_status);self.scene_tree=ttk.Treeview(frame,columns=("reason","id"),show="tree headings");self.scene_tree.heading("#0",text="场景 / 单词");self.scene_tree.heading("reason",text="分类理由");self.scene_tree.column("id",width=0,stretch=False);self.scene_tree.pack(fill="both",expand=True,pady=10)
        bar=ttk.Frame(frame);bar.pack(fill="x");
        for text,cmd in [("重命名",self.rename_scene),("移动",self.move_word),("合并",self.merge_scene),("拆分",self.split_scene),("确认分类",self.confirm_batch),("重新分类",self.reclassify)]:ttk.Button(bar,text=text,command=cmd).pack(side="left",padx=(0,6))
    def refresh_scenes(self):
        self.scene_tree.delete(*self.scene_tree.get_children());batch=self.batch
        if not batch:
            row=self.db.execute("SELECT id FROM import_batches WHERE status IN ('draft','confirmed') ORDER BY id DESC LIMIT 1").fetchone();batch=row[0] if row else None;self.batch=batch
        if not batch:self.scene_status.set("尚无分类结果");return
        status=self.db.execute("SELECT status FROM import_batches WHERE id=?",(batch,)).fetchone()[0];self.scene_status.set(f"批次 {batch} · {'待确认' if status=='draft' else '已确认'}；调整立即保存，不会自动重算")
        counts={r[0]:r[1] for r in self.db.execute("SELECT sw.word,count(*) FROM scene_words sw JOIN scenes s ON s.id=sw.scene_id WHERE s.batch_id=? GROUP BY sw.word",(batch,))}
        for scene in self.db.execute("SELECT id,name FROM scenes WHERE batch_id=? ORDER BY position,id",(batch,)):
            parent=self.scene_tree.insert("","end",text=scene["name"],values=("",f"scene:{scene['id']}"),open=True)
            for m in self.db.execute("SELECT word,reason FROM scene_words WHERE scene_id=? ORDER BY word",(scene["id"],)):self.scene_tree.insert(parent,"end",text=m["word"]+(" · 多场景" if counts.get(m["word"],0)>1 else ""),values=(m["reason"],f"word:{scene['id']}:{m['word']}"))
        missing=list(self.db.execute("SELECT word,reason FROM unclassified WHERE batch_id=?",(batch,)))
        if missing:
            parent=self.scene_tree.insert("","end",text="无法准确判断",values=("","unknown"),open=True)
            for m in missing:self.scene_tree.insert(parent,"end",text=m["word"],values=(m["reason"],"unknown"))
    def selected_scene(self):
        item=self.scene_tree.focus();raw=self.scene_tree.set(item,"id") if item else ""
        if raw.startswith("scene:"):return int(raw.split(":")[1])
        if raw.startswith("word:"):return int(raw.split(":")[1])
        return None
    def rename_scene(self):
        sid=self.selected_scene();
        if not sid:return messagebox.showinfo("请选择场景","先选择一个场景")
        old=self.db.execute("SELECT name FROM scenes WHERE id=?",(sid,)).fetchone()[0];name=simpledialog.askstring("重命名","新名称",initialvalue=old)
        if name and name.strip():self.db.execute("UPDATE scenes SET name=?,user_modified=1 WHERE id=?",(name.strip(),sid));self.db.commit();self.refresh_scenes()
    def move_word(self):
        item=self.scene_tree.focus();raw=self.scene_tree.set(item,"id") if item else ""
        if not raw.startswith("word:"):return messagebox.showinfo("请选择单词","在场景下选择一个单词")
        _,from_id,word=raw.split(":",2);targets=list(self.db.execute("SELECT id,name FROM scenes WHERE batch_id=? AND id<>?",(self.batch,from_id)))
        target=simpledialog.askstring("移动单词","目标场景名称\n"+"、".join(x["name"] for x in targets))
        match=next((x for x in targets if x["name"]==target),None)
        if match:
            with self.db:self.db.execute("INSERT OR REPLACE INTO scene_words SELECT ?,word,reason FROM scene_words WHERE scene_id=? AND word=?",(match["id"],from_id,word));self.db.execute("DELETE FROM scene_words WHERE scene_id=? AND word=?",(from_id,word));self.db.execute("UPDATE scenes SET user_modified=1 WHERE id IN (?,?)",(from_id,match["id"]))
            self.refresh_scenes()
    def merge_scene(self):
        sid=self.selected_scene();
        if not sid:return
        targets=list(self.db.execute("SELECT id,name FROM scenes WHERE batch_id=? AND id<>?",(self.batch,sid)));target=simpledialog.askstring("合并场景","合并到：\n"+"、".join(x["name"] for x in targets));match=next((x for x in targets if x["name"]==target),None)
        if match and messagebox.askyesno("确认合并",f"合并到“{target}”？"):
            with self.db:self.db.execute("INSERT OR IGNORE INTO scene_words SELECT ?,word,reason FROM scene_words WHERE scene_id=?",(match["id"],sid));self.db.execute("DELETE FROM scene_words WHERE scene_id=?",(sid,));self.db.execute("DELETE FROM scenes WHERE id=?",(sid,));self.db.execute("UPDATE scenes SET user_modified=1 WHERE id=?",(match["id"],))
            self.refresh_scenes()
    def split_scene(self):
        sid=self.selected_scene();
        if not sid:return
        name=simpledialog.askstring("拆分","新场景名称");words=simpledialog.askstring("拆分","移入新场景的单词，用逗号分隔") if name else None
        if name and words:
            selected=[core.normalize_word(x) for x in words.replace("，",",").split(",") if x.strip()]
            with self.db:
                cur=self.db.execute("INSERT INTO scenes(batch_id,name,position,user_modified) VALUES(?,?,999,1)",(self.batch,name.strip()));new=cur.lastrowid
                for word in selected:self.db.execute("INSERT OR REPLACE INTO scene_words SELECT ?,word,reason FROM scene_words WHERE scene_id=? AND word=?",(new,sid,word));self.db.execute("DELETE FROM scene_words WHERE scene_id=? AND word=?",(sid,word))
                self.db.execute("UPDATE scenes SET user_modified=1 WHERE id=?",(sid,))
            self.refresh_scenes()
    def confirm_batch(self):
        if self.batch:
            with self.db:self.db.execute("UPDATE import_batches SET status='confirmed',confirmed_at=? WHERE id=?",(date.today().isoformat(),self.batch))
            self.refresh_scenes()
    def reclassify(self):
        if self.batch:self.classify(self.batch,True)

    def _build_words(self):
        frame=ttk.Frame(self.word_tab,padding=16);frame.pack(fill="both",expand=True);self.label(frame,"我的单词本","Title.TLabel").pack(anchor="w");self.word_search=tk.StringVar();entry=ttk.Entry(frame,textvariable=self.word_search);entry.pack(fill="x",pady=8);entry.bind("<KeyRelease>",lambda e:self.refresh_words());self.word_tree=ttk.Treeview(frame,columns=("meaning","mastery","scenes"),show="headings");
        for c,n in [("meaning","单词与释义"),("mastery","熟悉程度"),("scenes","场景")]:self.word_tree.heading(c,text=n)
        self.word_tree.pack(fill="both",expand=True);self.word_tree.bind("<Double-1>",lambda e:self.word_detail());bar=ttk.Frame(frame);bar.pack(fill="x",pady=8);ttk.Button(bar,text="查看详情",command=self.word_detail).pack(side="left");ttk.Button(bar,text="标记熟悉",command=lambda:self.set_mastery(1)).pack(side="left",padx=6);ttk.Button(bar,text="标记已掌握",command=lambda:self.set_mastery(2)).pack(side="left")
    def refresh_words(self):
        self.word_tree.delete(*self.word_tree.get_children());q=self.word_search.get().lower() if hasattr(self,"word_search") else ""
        for r in self.db.execute("SELECT word,content,mastery FROM words ORDER BY word"):
            content=json.loads(r["content"]);scenes="、".join(x[0] for x in self.db.execute("SELECT s.name FROM scenes s JOIN scene_words sw ON sw.scene_id=s.id WHERE sw.word=?",(r["word"],)));line=f"{r['word']} — {content.get('meaning','')}"
            if q not in (line+scenes).lower():continue
            self.word_tree.insert("","end",iid=r["word"],values=(line,["学习中","熟悉","已掌握"][r["mastery"]],scenes))
    def selected_word(self):return self.word_tree.focus()
    def set_mastery(self,value):
        word=self.selected_word();
        if word:
            self.db.execute("UPDATE words SET mastery=? WHERE word=?",(value,word));self.db.commit();self.refresh_words()
            if value==2:
                row=self.db.execute("SELECT word FROM words WHERE mastery<2 AND word<>? ORDER BY CASE WHEN word>? THEN 0 ELSE 1 END,word LIMIT 1",(word,word)).fetchone()
                if row:self.word_tree.selection_set(row[0]);self.word_tree.focus(row[0]);self.word_tree.see(row[0]);self.word_detail()
                else:messagebox.showinfo("全部掌握","所有单词都已标记为掌握")
    def word_detail(self):
        word=self.selected_word();
        if not word:return
        r=self.db.execute("SELECT content FROM words WHERE word=?",(word,)).fetchone();content=json.loads(r[0]);scenes=list(self.db.execute("SELECT s.name,sw.reason FROM scenes s JOIN scene_words sw ON sw.scene_id=s.id WHERE sw.word=?",(word,)));links=list(self.db.execute("SELECT old_word,relation,reason,example FROM word_links WHERE new_word=?",(word,)))
        lines=[word,content.get("meaning","")]+[f"{k}: {content.get(k,'')}" for k in core.FIELDS[1:] if content.get(k)]+["","所属场景:"]+[f"• {x['name']} — {x['reason']}" for x in scenes]+["","关联旧词:"]+[f"• {x['old_word']} / {x['relation']}\n  {x['reason']}\n  {x['example']}" for x in links]
        messagebox.showinfo("词卡详情","\n".join(lines))

    def _build_review(self):
        frame=ttk.Frame(self.review_tab,padding=16);frame.pack(fill="both",expand=True);self.label(frame,"今天复习","Title.TLabel").pack(anchor="w");self.review_text=tk.Text(frame,wrap="word",font=("Microsoft YaHei UI",12),state="disabled");self.review_text.pack(fill="both",expand=True,pady=10);self.review_answer=tk.StringVar();ttk.Entry(frame,textvariable=self.review_answer,font=("Microsoft YaHei UI",12)).pack(fill="x",pady=(0,8));bar=ttk.Frame(frame);bar.pack();ttk.Button(bar,text="提交手工答案",command=self.reveal_review).pack(side="left");self.rating_buttons=[]
        for n,r in [("不认识",3),("有点模糊",2),("认识",1)]:button=ttk.Button(bar,text=n,command=lambda x=r:self.rate_review(x),state="disabled");button.pack(side="left",padx=4);self.rating_buttons.append(button)
    def refresh_review(self):
        self.review_row=self.db.execute("SELECT * FROM words WHERE due<=? ORDER BY due,word LIMIT 1",(date.today().isoformat(),)).fetchone();self.review_submitted=False;self.review_answer.set("")
        for button in self.rating_buttons:button.configure(state="disabled")
        if self.review_row:
            content=json.loads(self.review_row["content"]);self._set_review((content.get("quiz") or self.review_row["word"])+"\n\n请手工输入答案，提交后查看参考答案。")
        else:self._set_review("今天的复习完成了。")
    def _set_review(self,s):self.review_text.configure(state="normal");self.review_text.delete("1.0","end");self.review_text.insert("1.0",s);self.review_text.configure(state="disabled")
    def reveal_review(self):
        if not self.review_row:return
        typed=self.review_answer.get().strip()
        if not typed:return messagebox.showinfo("请输入答案","提交前需要手工输入答案")
        word=self.review_row["word"];content=json.loads(self.review_row["content"]);scenes="\n".join("• "+x[0]+" — "+x[1] for x in self.db.execute("SELECT s.name,sw.reason FROM scenes s JOIN scene_words sw ON sw.scene_id=s.id WHERE sw.word=?",(word,)));links="\n".join("• "+x[0]+" — "+x[1]+"\n  "+x[2] for x in self.db.execute("SELECT old_word,reason,example FROM word_links WHERE new_word=?",(word,)));self._set_review(f"你的答案\n{typed}\n\n参考答案\n{content.get('answer') or word}\n\n{word} — {content.get('meaning','')}\n{content.get('example','')}\n{content.get('translation','')}\n\n场景\n{scenes or '暂无'}\n\n关联旧词\n{links or '暂无合理关联'}");self.review_submitted=True
        for button in self.rating_buttons:button.configure(state="normal")
    def rate_review(self,rating):
        if not self.review_row or not self.review_submitted:return messagebox.showinfo("先提交答案","需要先手工输入并提交答案")
        stage,due=core.schedule(self.review_row["stage"],rating,date.today());mastery=max(self.review_row["mastery"],1 if rating==1 else 0);self.db.execute("UPDATE words SET stage=?,due=?,mastery=? WHERE word=?",(stage,due,mastery,self.review_row["word"]));self.db.commit();self.refresh_review();self.refresh_words()

    def _build_api(self):
        frame=ttk.Frame(self.api_tab,padding=16);frame.pack(fill="both",expand=True);self.label(frame,"API 设置","Title.TLabel").grid(row=0,column=0,columnspan=2,sticky="w");self.label(frame,"验证成功后使用 Windows DPAPI 加密保存密钥。页面和错误不会显示完整密钥。","Sub.TLabel").grid(row=1,column=0,columnspan=2,sticky="w",pady=(0,12));self.api_vars={}
        self.profile_choice=tk.StringVar();self.profile_box=ttk.Combobox(frame,textvariable=self.profile_choice,state="readonly");self.profile_box.grid(row=2,column=1,sticky="ew",pady=5);self.profile_box.bind("<<ComboboxSelected>>",lambda e:self.select_profile());self.label(frame,"已有配置").grid(row=2,column=0,sticky="w")
        for row,(key,label) in enumerate([("name","配置名称"),("base","Base URL"),("model","模型名称"),("key","新 API Key（留空保留）")],3):self.label(frame,label).grid(row=row,column=0,sticky="w",pady=5);v=tk.StringVar();self.api_vars[key]=v;ttk.Entry(frame,textvariable=v,show="•" if key=="key" else "").grid(row=row,column=1,sticky="ew",pady=5)
        self.api_protocol=tk.StringVar(value="responses");ttk.Combobox(frame,textvariable=self.api_protocol,values=("responses","chat"),state="readonly").grid(row=7,column=1,sticky="ew");self.label(frame,"接口格式").grid(row=7,column=0,sticky="w");frame.columnconfigure(1,weight=1);bar=ttk.Frame(frame);bar.grid(row=8,column=0,columnspan=2,sticky="w",pady=14);ttk.Button(bar,text="验证并保存",command=self.save_api).pack(side="left");ttk.Button(bar,text="新建配置",command=self.new_api_profile).pack(side="left",padx=8);ttk.Button(bar,text="清除密钥",command=self.clear_api_key).pack(side="left");ttk.Button(bar,text="删除配置",command=self.delete_api_profile).pack(side="left",padx=8);self.load_api()
    def load_api(self):
        names=[r[0] for r in self.db.execute("SELECT name FROM api_profiles ORDER BY name")];self.profile_box.configure(values=names)
        p=self.active_profile()
        if p:
            self.profile_choice.set(p["name"])
            for k in ("name","base","model"):self.api_vars[k].set(p[k])
            self.api_protocol.set(p["protocol"]);self.api_vars["key"].set("")
    def select_profile(self):
        name=self.profile_choice.get()
        with self.db:self.db.execute("UPDATE api_profiles SET is_active=CASE WHEN name=? THEN 1 ELSE 0 END",(name,))
        self.load_api()
    def new_api_profile(self):
        self.profile_choice.set("")
        for key in self.api_vars:self.api_vars[key].set("")
        self.api_vars["base"].set("https://api.openai.com/v1");self.api_vars["model"].set("gpt-4.1-mini");self.api_protocol.set("responses")
    def save_api(self):
        old=self.active_profile() if self.profile_choice.get() else None;old_name=old["name"] if old else "";name=self.api_vars["name"].get().strip();base=self.api_vars["base"].get().strip();model=self.api_vars["model"].get().strip();protocol=self.api_protocol.get();key=self.api_vars["key"].get().strip() or self.keys.get(old_name,"")
        if not all((name,base,model,key)):return messagebox.showwarning("缺少设置","请完整填写首次配置")
        if name!=old_name and self.db.execute("SELECT 1 FROM api_profiles WHERE name=?",(name,)).fetchone():return messagebox.showwarning("名称重复","这个配置名称已经存在")
        try:core.endpoint(base,protocol)
        except Exception as exc:return messagebox.showerror("地址错误",str(exc))
        self.async_run(lambda:core.verify_key(base,model,protocol,key),lambda _ :self._api_saved(old_name,name,base,model,protocol,key))
    def _api_saved(self,old,name,base,model,protocol,key):
        with self.db:
            self.db.execute("UPDATE api_profiles SET is_active=0")
            if old and old!=name:self.db.execute("DELETE FROM api_profiles WHERE name=?",(old,))
            self.db.execute("INSERT OR REPLACE INTO api_profiles VALUES(?,?,?,?,1)",(name,base,model,protocol))
        if old and old!=name:self.keys.pop(old,None)
        self.keys[name]=key;self._save_keys();self.load_api();messagebox.showinfo("已保存","密钥验证成功并已加密保存")
    def clear_api_key(self):
        p=self.active_profile();
        if p and messagebox.askyesno("清除密钥","清除后下次调用 AI 需要重新输入，继续吗？"):self.keys.pop(p["name"],None);self._save_keys();messagebox.showinfo("已清除","词库和分类未改变")
    def delete_api_profile(self):
        p=self.active_profile();count=self.db.execute("SELECT count(*) FROM api_profiles").fetchone()[0]
        if not p or count<=1:return messagebox.showinfo("无法删除","至少保留一个 API 配置")
        if messagebox.askyesno("删除配置",f"删除“{p['name']}”及其已保存密钥？"):
            self.keys.pop(p["name"],None);self._save_keys()
            with self.db:self.db.execute("DELETE FROM api_profiles WHERE name=?",(p["name"],));self.db.execute("UPDATE api_profiles SET is_active=1 WHERE name=(SELECT name FROM api_profiles ORDER BY name LIMIT 1)")
            self.load_api()

    def refresh_all(self):self.refresh_scenes();self.refresh_words();self.refresh_review()
    def close(self):self.db.close();self.destroy()

if __name__=="__main__":App().mainloop()
