#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模式分析（第三版，基于逐条投递记录 application_log / application_events）
只读 job_search_tracker.db，不查 Gmail。重跑：python3 analysis.py
注意：2026-09 的投递还在进行中，按投递批次算比例时排除。
"""
import sqlite3, os, re, statistics as st

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job_search_tracker.db")
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()
pct = lambda a, b: f"{100*a/b:.1f}%" if b else "-"

print("=== 0. 总量 ===")
for ch, n in q("SELECT channel, COUNT(*) FROM application_log GROUP BY 1 ORDER BY 2 DESC"):
    print(f"{ch}: {n}")
print("合计:", q("SELECT COUNT(*) FROM application_log")[0][0])
ats = q("SELECT COUNT(*) FROM application_events WHERE type='ats_ack'")[0][0]
print(f"另有 {ats} 封公司官网/ATS 确认邮件，未计入上面的投递数（未清洗，含重复和提醒邮件）")

print("\n=== 1. 每份投递的最终结果（按投递批次，不含 2026-09）===")
for ch in ("JobStreet", "LinkedIn", "直投邮件"):
    rows = dict(q("""SELECT outcome, COUNT(*) FROM application_log
                     WHERE channel=? AND applied_month<'2026-09' GROUP BY 1""", (ch,)))
    n = sum(rows.values())
    print(ch, n, {k: f"{v} ({pct(v, n)})" for k, v in sorted(rows.items(), key=lambda x: -x[1])})

print("\n=== 2. 硕士毕业前后（JobStreet，按投递批次）===")
for g, cond in (("毕业前 2025-03~12", "applied_month<'2026-01'"),
                ("毕业后 2026-01~08", "applied_month>='2026-01' AND applied_month<'2026-09'")):
    n, rej, vw, exp = q(f"""SELECT COUNT(*), SUM(rejected_at IS NOT NULL), SUM(viewed_at IS NOT NULL),
                            SUM(outcome='expired_no_reply') FROM application_log
                            WHERE channel='JobStreet' AND {cond}""")[0]
    print(f"{g}: 投递 {n}，被拒 {pct(rej, n)}，被查看 {pct(vw, n)}，过期无回音 {pct(exp, n)}")

print("\n=== 3. JobStreet 拒信：多快到、拒之前雇主有没有打开过 ===")
d = sorted(r[0] for r in q("SELECT days_to_reject FROM application_log WHERE channel='JobStreet' AND days_to_reject IS NOT NULL"))
print(f"拒信 {len(d)} 封，投递到拒信中位数 {st.median(d):.1f} 天，四分位 {d[len(d)//4]:.1f}–{d[3*len(d)//4]:.1f} 天")
seen, unseen = q("""SELECT SUM(viewed_at IS NOT NULL AND viewed_at<=rejected_at), SUM(viewed_at IS NULL OR viewed_at>rejected_at)
                    FROM application_log WHERE channel='JobStreet' AND rejected_at IS NOT NULL""")[0]
print(f"拒信前收到过'雇主已查看'通知：{seen}（{pct(seen, len(d))}）；没收到：{unseen}（{pct(unseen, len(d))}）")

print("\n=== 4. 面试邀约从哪来（邮件里能查到的）===")
def core(s):
    s = re.sub(r"[^\w ]", " ", (s or "").lower())
    stop = {"pte", "ltd", "singapore", "group", "inc", "the", "company", "engineering", "management", "s"}
    return [t for t in s.split() if t not in stop]
ats_rows = q("SELECT event_at, lower(coalesce(subject,'')||' '||coalesce(sender,'')) FROM application_events WHERE type='ats_ack'")
src_count = {}
for when, comp, title, app_ch in q("""SELECT e.event_at, e.company, e.job_title, a.channel FROM application_events e
                                      LEFT JOIN application_log a ON a.app_id=e.app_id WHERE e.type='interview' ORDER BY 1"""):
    if app_ch:
        src = app_ch
    else:
        toks = core(comp)
        hit = any(toks and toks[0] in txt and at <= when for at, txt in ats_rows)
        src = "公司官网/ATS" if hit else "其他（猎头、内推、平台外联系等，邮件里无投递记录）"
    src_count[src] = src_count.get(src, 0) + 1
    print(f"  {when[:10]}  {comp}  |  {title or '-'}  |  来源：{src}")
print("来源汇总：", src_count)
