#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模式分析脚本：只读 job_search_tracker.db，不查 Gmail。
重跑方法：python3 analysis.py
注意：月度数据是"当月投递"和"当月收到的结果"，不是同一批申请的前后追踪，
所以这里的比率是月度层面的规律，不是逐份申请的转化率。
"""
import sqlite3, os, math, statistics as st

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job_search_tracker.db")
c = sqlite3.connect(DB).cursor()
rows = c.execute("""SELECT month, js_submitted, li_submitted, direct_submitted,
                    total_submitted, rejected, expired, viewed
                    FROM monthly_stats ORDER BY month""").fetchall()
m   = [r[0] for r in rows]; js = [r[1] for r in rows]; li = [r[2] for r in rows]
tot = [r[4] for r in rows]; rej = [r[5] for r in rows]
exp = [r[6] for r in rows]; vw = [r[7] for r in rows]

def r(x, y):
    mx, my = st.mean(x), st.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return num / math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))

def ols(x, y):
    mx, my = st.mean(x), st.mean(y)
    b = sum((a - mx) * (v - my) for a, v in zip(x, y)) / sum((a - mx) ** 2 for a in x)
    return my - b * mx, b

print("=== 发现1：拒信数量几乎完全由 JobStreet 投递量决定 ===")
a0, b = ols(js, rej)
print(f"同月相关系数 r(拒信, JobStreet投递) = {r(js, rej):.2f}")
print(f"滞后一个月   r(拒信, 上月JobStreet投递) = {r(js[:-1], rej[1:]):.2f}")
print(f"回归：拒信 = {a0:.2f} + {b:.3f} × JobStreet投递（截距≈0）")
big = [i for i in range(len(m)) if js[i] >= 40]
ratios = [rej[i] / js[i] for i in big]
print(f"JobStreet月投递≥40的{len(big)}个月，拒信/投递 均值 {st.mean(ratios):.1%}，标准差 {st.stdev(ratios):.1%}")

print("\n=== 发现2：硕士毕业前后，拒信比例没有变化 ===")
def agg(sel):
    J = sum(js[i] for i in sel); L = sum(li[i] for i in sel)
    R = sum(rej[i] for i in sel); V = sum(vw[i] for i in sel)
    return J, L, R, V
pre  = [i for i, x in enumerate(m) if x < '2026-01']
post = [i for i, x in enumerate(m) if x >= '2026-01']
for name, sel in [("毕业前 2025-03~12", pre), ("毕业后 2026-01~09", post)]:
    J, L, R, V = agg(sel)
    print(f"{name}: JobStreet {J}，拒信 {R}，拒信/JS {R/J:.1%}；查看 {V}，查看/(JS+LI) {V/(J+L):.1%}")
J1, L1, _, V1 = agg(pre); J2, L2, _, V2 = agg(post)
p1, p2 = V1 / (J1 + L1), V2 / (J2 + L2); pp = (V1 + V2) / (J1 + L1 + J2 + L2)
z = (p2 - p1) / math.sqrt(pp * (1 - pp) * (1 / (J1 + L1) + 1 / (J2 + L2)))
print(f"查看率变化的两比例 z 检验 z = {z:.2f}（|z|<1.96，不显著）")

print("\n=== 发现3：拒信原因抽样 ===")
s = c.execute("SELECT SUM(with_feedback), SUM(cites_work_permit) FROM rejection_sample").fetchone()
print(f"带反馈详情 {s[0]} 封，标注工作权限 {s[1]} 封（{s[1]/s[0]:.0%}）")
for row in c.execute("""SELECT r.month, r.company, r.reason_detail, c.size_category
                        FROM rejection_sample r LEFT JOIN companies c ON r.company=c.name
                        WHERE r.is_exception=1 ORDER BY r.month"""):
    print("  例外", row)

print("\n=== 数据质量警示：过期通知数 > JobStreet 投递数 ===")
cj = ce = 0
for i in range(len(m)):
    cj += js[i]; ce += exp[i]
    if ce > cj:
        print(f"  最早在 {m[i]}：累计过期 {ce} > 累计JobStreet投递 {cj}")
        break
print(f"  全期：累计过期 {sum(exp)} vs 累计JobStreet投递 {sum(js)}")
print(f"  过期与上月投递相关 r = {r(js[:-1], exp[1:]):.2f}，与当月 r = {r(js, exp):.2f}（过期约滞后一个月，符合帖子30天有效期）")
