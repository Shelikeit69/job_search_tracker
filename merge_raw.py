#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 raw/*.jsonl（多轮独立提取的 Gmail 元数据）合并成逐条记录：
  applications_all.jsonl  —— 每份投递一行
  events_all.jsonl        —— 每条结果通知一行（拒信/查看/过期/面试/ATS确认）
规则：
  - 按 Gmail message id 去重；同一 id 在多个文件出现的，记录 n_sources 作为交叉验证
  - 日期统一换算成新加坡时间 (UTC+8) 再分月
  - 公司/职位从邮件标题解析；标题里有歧义（职位本身带 " at " 等）时，
    优先选能和已有投递对上的切分方式
不调用 Gmail，只读 raw 文件。
"""
import json, glob, os, re, html, collections, datetime

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
OUT = os.path.dirname(os.path.abspath(__file__))

def load(pattern):
    for f in sorted(glob.glob(os.path.join(RAW, pattern))):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if "error" in r or not r.get("msg_id"):
                continue
            yield os.path.basename(f), r

def clean(s):
    if s is None:
        return None
    s = html.unescape(str(s))
    s = re.sub(r"\s+", " ", s).strip()
    return s or None

def norm(s):
    s = clean(s) or ""
    s = s.lower().replace("（", "(").replace("）", ")")
    s = re.sub(r"[^\w()&+/ ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def sgt(date_utc):
    d = datetime.datetime.fromisoformat(date_utc.replace("Z", "+00:00"))
    return (d + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

# ---------- 1. 收集各类别（按 msg_id 去重） ----------
cats = collections.defaultdict(dict)   # cat -> msg_id -> {"r": merged, "src": set()}

def put(cat, fname, r, **fields):
    mid = r["msg_id"]
    slot = cats[cat].setdefault(mid, {"r": {"msg_id": mid, "thread_id": r.get("thread_id"),
                                            "date_utc": r.get("date")}, "src": set()})
    slot["src"].add(fname)
    for k, v in fields.items():
        v = clean(v)
        if v and not slot["r"].get(k):
            slot["r"][k] = v

for fname, r in load("*.jsonl"):
    c, s, t = r.get("cat"), r.get("source"), r.get("type")
    subj = r.get("subject")
    if c == "js_submit" or s == "jobstreet_submitted":
        put("js_sub", fname, r, company=r.get("company"), title=r.get("title") or r.get("job_title"), raw=r.get("raw"))
    elif c == "li_submit" or s == "linkedin_sent":
        put("li_sub", fname, r, company=r.get("company"), subject=subj)
    elif s == "direct_email":
        put("direct_app", fname, r, company=r.get("company"), title=r.get("job_title"), to=r.get("to"), subject=r.get("raw"))
    elif c == "sent_attach":
        put("sent_attach", fname, r, to=r.get("to"), subject=subj, snippet=r.get("snippet"))
    elif fname == "direct_excluded.jsonl":
        put("direct_excl", fname, r, to=r.get("to"), subject=r.get("subject"), reason=r.get("reason"))
    elif c == "ats_ack":
        put("ats_ack", fname, r, sender=r.get("sender"), subject=subj, snippet=r.get("snippet"))
    elif c == "js_reject" or (s == "jobstreet" and t == "rejected"):
        put("js_rej", fname, r, company=r.get("company"), title=r.get("job_title"), subject=subj)
    elif c == "js_viewed" or (s == "jobstreet" and t == "viewed"):
        put("js_view", fname, r, company=r.get("company"), title=r.get("job_title"), subject=subj)
    elif c == "js_expired" or (s == "jobstreet" and t == "expired"):
        put("js_exp", fname, r, company=r.get("company"), title=r.get("job_title"), subject=subj)
    elif c == "li_reject" or (s == "linkedin" and t == "rejected"):
        put("li_rej", fname, r, company=r.get("company"), title=r.get("job_title"), subject=subj)
    elif c == "li_viewed" or (s == "linkedin" and t == "viewed"):
        put("li_view", fname, r, company=r.get("company"), subject=subj or r.get("raw"))
    elif c == "direct_reject":
        put("direct_rej", fname, r, company=r.get("company"), title=r.get("job_title"), sender=r.get("sender"), subject=subj)
    elif c == "interview":
        put("interview", fname, r, company=r.get("company"), title=r.get("job_title"), sender=r.get("sender"), subject=subj)
    else:
        put("other", fname, r, subject=subj or r.get("raw"))

# ---------- 2. 解析标题 ----------
js_keys = {(norm(v["r"].get("title")), norm(v["r"].get("company"))) for v in cats["js_sub"].values()}

def split_candidates(text, sep):
    parts = text.split(sep)
    return [(sep.join(parts[:i]), sep.join(parts[i:])) for i in range(1, len(parts))]

def best_split(text, sep, known_keys, title_first=True):
    """多个切分点时，优先选能和已知投递(职位,公司)对上的；否则取最后一个分隔符"""
    cands = split_candidates(text, sep)
    if not cands:
        return None, None
    for a, b in cands:
        t, co = (a, b) if title_first else (b, a)
        if (norm(t), norm(co)) in known_keys:
            return clean(t), clean(co)
    a, b = cands[-1] if title_first else cands[0]
    t, co = (a, b) if title_first else (b, a)
    return clean(t), clean(co)

for v in cats["js_sub"].values():
    r = v["r"]
    if (not r.get("title") or not r.get("company")) and r.get("raw"):
        m = re.search(r"application for (.+?) was successfully submitted to (.+?)(?: jobstreet|$)", r["raw"])
        if m:
            r.setdefault("title", clean(m.group(1))); r.setdefault("company", clean(m.group(2)))

for v in cats["js_rej"].values():
    r = v["r"]
    if not (r.get("title") and r.get("company")) and r.get("subject"):
        body = re.sub(r"^Application update for ", "", r["subject"])
        r["title"], r["company"] = best_split(body, " at ", js_keys)

for v in cats["js_view"].values():
    r = v["r"]
    if not (r.get("title") and r.get("company")) and r.get("subject"):
        m = re.match(r"(.+?) has viewed your application for (.+)$", r["subject"])
        if m:
            r["company"], r["title"] = clean(m.group(1)), clean(m.group(2))

for v in cats["js_exp"].values():
    r = v["r"]
    s = r.get("subject") or ""
    if "new activity in jobs you applied for" in s:
        r["digest"] = True
        continue
    if not (r.get("title") and r.get("company")):
        m = re.match(r"Hi \w+, the (.+) has closed$", s)
        if m:
            r["title"], r["company"] = best_split(m.group(1), " job with ", js_keys)

for v in cats["li_sub"].values():
    r = v["r"]
    if not r.get("company") and r.get("subject"):
        m = re.search(r"application was sent to (.+)$", r["subject"])
        if m:
            r["company"] = clean(m.group(1))

li_companies = {norm(v["r"].get("company")) for v in cats["li_sub"].values()}
li_keys = {(t, c) for t in [""] for c in li_companies}

for v in cats["li_rej"].values():
    r = v["r"]
    if not (r.get("title") and r.get("company")) and r.get("subject"):
        body = re.sub(r"^Your application to ", "", r["subject"])
        cands = split_candidates(body, " at ")
        pick = None
        for a, b in cands:
            if norm(b) in li_companies:
                pick = (a, b); break
        if not pick and cands:
            pick = cands[-1]
        if pick:
            r["title"], r["company"] = clean(pick[0]), clean(pick[1])

for v in cats["li_view"].values():
    r = v["r"]
    if not r.get("company") and r.get("subject"):
        m = re.search(r"viewed by (.+)$", r["subject"])
        if m:
            r["company"] = clean(m.group(1))

# ---------- 3. 输出 ----------
def rows(cat):
    for mid, v in cats[cat].items():
        r = dict(v["r"])
        r["n_sources"] = len(v["src"])
        r["sources"] = sorted(v["src"])
        r["date_sgt"] = sgt(r["date_utc"])
        yield r

apps, events = [], []
for r in rows("js_sub"):
    apps.append({**r, "channel": "JobStreet"})
for r in rows("li_sub"):
    apps.append({**r, "channel": "LinkedIn", "title": None})
direct_ids = set(cats["direct_app"])
for r in rows("direct_app"):
    apps.append({**r, "channel": "直投邮件"})

etype = {"js_rej": ("JobStreet", "rejected"), "js_view": ("JobStreet", "viewed"),
         "js_exp": ("JobStreet", "expired"), "li_rej": ("LinkedIn", "rejected"),
         "li_view": ("LinkedIn", "viewed"), "direct_rej": ("direct", "rejected"),
         "interview": ("direct", "interview"), "ats_ack": ("company_ats", "ats_ack")}
for cat, (ch, t) in etype.items():
    for r in rows(cat):
        events.append({**r, "channel": ch, "type": t})

with open(os.path.join(OUT, "applications_all.jsonl"), "w", encoding="utf-8") as f:
    for a in sorted(apps, key=lambda x: x["date_utc"]):
        f.write(json.dumps(a, ensure_ascii=False) + "\n")
with open(os.path.join(OUT, "events_all.jsonl"), "w", encoding="utf-8") as f:
    for e in sorted(events, key=lambda x: x["date_utc"]):
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

# 没被分类的带附件发件
unclassified = [r for r in rows("sent_attach") if r["msg_id"] not in direct_ids and r["msg_id"] not in cats["direct_excl"]]
with open(os.path.join(OUT, "raw", "_sent_attach_unclassified.json"), "w", encoding="utf-8") as f:
    json.dump(unclassified, f, ensure_ascii=False, indent=1)

print("applications:", collections.Counter(a["channel"] for a in apps))
print("events:", collections.Counter((e["channel"], e["type"]) for e in events))
print("sent_attach 未分类:", len(unclassified))
print("other:", len(cats["other"]))
missing = [a for a in apps if a["channel"] == "JobStreet" and not (a.get("title") and a.get("company"))]
print("JobStreet 投递缺职位/公司:", len(missing))
for cat in ("js_rej", "js_exp", "js_view", "li_rej", "li_view"):
    miss = sum(1 for v in cats[cat].values() if not v["r"].get("company") and not v["r"].get("digest"))
    print(f"{cat} 未解析出公司:", miss)
