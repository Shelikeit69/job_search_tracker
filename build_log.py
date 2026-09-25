#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 merge_raw.py 输出的逐条记录写进数据库，并把结果通知匹配回对应的投递。
新增两张表：
  application_log     每份投递一行（含最终结果）
  application_events  每条结果通知一行（拒信/查看/过期/面试/ATS确认），带匹配到的 app_id
运行顺序：python3 build_db.py && python3 merge_raw.py && python3 build_log.py
"""
import json, os, re, sqlite3, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "job_search_tracker.db")

apps = [json.loads(l) for l in open(os.path.join(HERE, "applications_all.jsonl"), encoding="utf-8")]
events = [json.loads(l) for l in open(os.path.join(HERE, "events_all.jsonl"), encoding="utf-8")]

def norm(s):
    s = (s or "").lower().replace("（", "(").replace("）", ")")
    s = re.sub(r"[^\w()&+/ ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

SUFFIX = {"pte", "ltd", "limited", "private", "singapore", "s", "sg", "inc", "co", "company",
          "corporation", "corp", "llp", "llc", "plc", "the", "asia", "pacific", "apac", "group",
          "holdings", "holding", "international", "services", "service"}
def core(s):
    toks = [t for t in re.sub(r"[()&+/]", " ", norm(s)).split() if t not in SUFFIX]
    return " ".join(toks)

apps.sort(key=lambda a: a["date_utc"])
for i, a in enumerate(apps, 1):
    a["app_id"] = i
    a["key_tc"] = (norm(a.get("title")), norm(a.get("company")))
    a["core"] = core(a.get("company"))

by_tc = collections.defaultdict(list)       # JobStreet: (title, company)
by_co = collections.defaultdict(list)       # LinkedIn: company
by_core = collections.defaultdict(list)     # 所有渠道：公司核心词
for a in apps:
    if a["channel"] == "JobStreet":
        by_tc[a["key_tc"]].append(a)
    if a["channel"] == "LinkedIn":
        by_co[norm(a.get("company"))].append(a)
    if a["core"]:
        by_core[a["core"]].append(a)

def ts(x):
    return datetime.datetime.fromisoformat(x.replace("Z", "+00:00"))

def latest_before(cands, when):
    ok = [c for c in cands if c["date_utc"] <= when]
    return ok[-1] if ok else None

def match(e):
    when = e["date_utc"]
    if e["channel"] == "JobStreet":
        a = latest_before(by_tc.get((norm(e.get("title")), norm(e.get("company"))), []), when)
        if a:
            return a, "title+company"
        return None, None
    if e["channel"] == "LinkedIn":
        a = latest_before(by_co.get(norm(e.get("company")), []), when)
        if a:
            return a, "company(linkedin)"
        return None, None
    c = core(e.get("company"))
    if not c:
        return None, None
    cands = list(by_core.get(c, []))
    if not cands:
        for k, v in by_core.items():
            if len(c) >= 4 and len(k) >= 4 and (c in k or k in c):
                cands += v
        cands.sort(key=lambda a: a["date_utc"])
    a = latest_before(cands, when)
    # 只按公司名模糊匹配时，限定投递在通知前60天内，避免把几个月后的面试/拒信挂到很早的旧投递上
    if a and (ts(when) - ts(a["date_utc"])).days > 60:
        return None, None
    return (a, "company_fuzzy") if a else (None, None)

matched = collections.Counter(); unmatched = collections.Counter()
for e in events:
    if e.get("digest"):
        e["app_id"], e["match_method"] = None, "digest_skip"
        continue
    a, how = match(e)
    e["app_id"] = a["app_id"] if a else None
    e["match_method"] = how
    (matched if a else unmatched)[(e["channel"], e["type"])] += 1

# 汇总到每份投递
ev_by_app = collections.defaultdict(list)
for e in events:
    if e.get("app_id"):
        ev_by_app[e["app_id"]].append(e)

for a in apps:
    evs = sorted(ev_by_app.get(a["app_id"], []), key=lambda e: e["date_utc"])
    first = lambda t: next((e for e in evs if e["type"] == t), None)
    v, r, x, iv = first("viewed"), first("rejected"), first("expired"), first("interview")
    a["viewed_at"] = v["date_sgt"] if v else None
    a["rejected_at"] = r["date_sgt"] if r else None
    a["expired_at"] = x["date_sgt"] if x else None
    a["interview_at"] = iv["date_sgt"] if iv else None
    a["days_to_reject"] = round((ts(r["date_utc"]) - ts(a["date_utc"])).total_seconds() / 86400, 1) if r else None
    if iv: a["outcome"] = "interview"
    elif r: a["outcome"] = "rejected"
    elif x: a["outcome"] = "expired_no_reply"
    elif v: a["outcome"] = "viewed_no_decision"
    else: a["outcome"] = "no_response"
    # LinkedIn 投递标题：从 LinkedIn 拒信标题里补
    if a["channel"] == "LinkedIn" and not a.get("title"):
        t = next((e.get("title") for e in evs if e["channel"] == "LinkedIn" and e.get("title")), None)
        if t:
            a["title"], a["title_source"] = t, "来自 LinkedIn 拒信标题"

con = sqlite3.connect(DB)
con.executescript("""
DROP TABLE IF EXISTS application_log;
DROP TABLE IF EXISTS application_events;
CREATE TABLE application_log (
  app_id INTEGER PRIMARY KEY,
  channel TEXT,             -- JobStreet / LinkedIn / 直投邮件
  applied_at TEXT,          -- 新加坡时间
  applied_month TEXT,
  company TEXT,
  job_title TEXT,           -- LinkedIn 大多为空（确认邮件标题不含职位）
  title_source TEXT,
  outcome TEXT,             -- interview / rejected / expired_no_reply / viewed_no_decision / no_response
  viewed_at TEXT, rejected_at TEXT, expired_at TEXT, interview_at TEXT,
  days_to_reject REAL,
  gmail_msg_id TEXT, gmail_thread_id TEXT,
  n_sources INTEGER         -- 几轮独立提取里出现过（≥2 表示交叉验证过）
);
CREATE TABLE application_events (
  event_id INTEGER PRIMARY KEY,
  channel TEXT,             -- JobStreet / LinkedIn / direct / company_ats
  type TEXT,                -- rejected / viewed / expired / interview / ats_ack
  event_at TEXT,            -- 新加坡时间
  event_month TEXT,
  company TEXT, job_title TEXT, sender TEXT, subject TEXT,
  app_id INTEGER,           -- 匹配到的投递，匹配不上为空
  match_method TEXT,
  gmail_msg_id TEXT, gmail_thread_id TEXT, n_sources INTEGER
);
""")
con.executemany("INSERT INTO application_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
    (a["app_id"], a["channel"], a["date_sgt"], a["date_sgt"][:7], a.get("company"), a.get("title"),
     a.get("title_source") or ("邮件标题/摘要" if a.get("title") else None), a["outcome"],
     a["viewed_at"], a["rejected_at"], a["expired_at"], a["interview_at"], a["days_to_reject"],
     a["msg_id"], a.get("thread_id"), a["n_sources"]) for a in apps])
con.executemany("INSERT INTO application_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
    (i, e["channel"], e["type"], e["date_sgt"], e["date_sgt"][:7], e.get("company"), e.get("title"),
     e.get("sender"), e.get("subject"), e.get("app_id"), e.get("match_method"),
     e["msg_id"], e.get("thread_id"), e["n_sources"])
    for i, e in enumerate(sorted(events, key=lambda e: e["date_utc"]), 1)])
con.execute("INSERT OR REPLACE INTO meta VALUES ('application_log_as_of', ?)",
            (max(a["date_sgt"] for a in apps)[:10],))
con.execute("INSERT OR REPLACE INTO meta VALUES ('application_log_note', ?)",
            ("逐条记录由多轮独立 Gmail 提取合并，按 message id 去重；抽查的 message id 均与 Gmail 原邮件一致。"
             "LinkedIn 确认邮件不含职位名，职位只在有 LinkedIn 拒信时才补上。",))
con.execute("INSERT OR REPLACE INTO meta VALUES ('monthly_stats_superseded', ?)",
            ("monthly_stats 是旧看板的月度汇总，JobStreet 投递严重少计（912 vs 逐条 1592），"
             "原因是当时用搜索预览计数，每个按天合并的邮件线程只数到前5封。以 application_log 为准。",))
con.execute("INSERT OR REPLACE INTO meta VALUES ('ats_ack_note', ?)",
            ("application_events 里 type='ats_ack' 的 268 封是公司官网/ATS 的投递确认，"
             "尚未清洗成投递记录（有重复、提醒邮件），所以没计入 application_log。",))
con.execute("INSERT OR REPLACE INTO meta VALUES ('direct_events_note', ?)",
            ("direct 渠道的拒信/面试由模型从邮件内容判断，按公司名模糊匹配（限60天内），可信度低于 JobStreet/LinkedIn 平台通知。",))
con.commit()

print("投递:", collections.Counter(a["channel"] for a in apps))
print("结果:", collections.Counter((a["channel"], a["outcome"]) for a in apps))
print("匹配上:", dict(matched))
print("未匹配:", dict(unmatched))
