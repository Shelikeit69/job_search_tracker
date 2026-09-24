#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性构建 job_search_tracker.db，数据全部来自已经核实过的来源：
  1. full-history-dashboard.html 的月度统计数组（2026-09-23 生成，Gmail 检索核实）
  2. full-history-dashboard.html 的拒信原因抽样表格（75封邮件逐封读正文核实）
  3. 上一轮公司中文名核实研究（subagent 网络调研，已核实/未核实分开记录）
  4. memory /areas/*.md 的摘要描述（当前在跟进的投递，2026-09 前后）

不做任何新的 Gmail 全量扫描；后续如需扩充例外样本之外的公司名，走增量更新脚本。
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "job_search_tracker.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
with open(SCHEMA_PATH, encoding="utf-8") as f:
    conn.executescript(f.read())

# ---------------------------------------------------------------
# 1) monthly_stats —— 来自 dashboard 里的 JS 数组，一一对应
# ---------------------------------------------------------------
labels    = ['2025-03','2025-04','2025-05','2025-06','2025-07','2025-08','2025-09','2025-10',
             '2025-11','2025-12','2026-01','2026-02','2026-03','2026-04','2026-05','2026-06',
             '2026-07','2026-08','2026-09']
js        = [10,15,3,6,5,10,108,68,61,92,92,61,78,76,26,40,48,13,100]
li        = [0,6,2,20,8,77,108,60,45,120,85,51,57,39,19,36,27,0,23]
direct    = [0,1,0,0,0,0,0,3,0,3,2,1,0,5,3,1,2,0,10]
rejected  = [2,9,2,0,3,4,61,43,42,47,43,30,48,65,15,14,29,13,54]
expired   = [7,14,20,6,8,2,35,134,84,104,82,83,61,83,82,22,49,46,42]
viewed    = [5,1,0,0,4,12,32,18,23,25,27,12,30,24,8,8,11,4,30]

rows = []
for i, m in enumerate(labels):
    total = js[i] + li[i] + direct[i]
    partial = 1 if m == '2026-09' else 0
    as_of = '2026-09-23' if not partial else '2026-09-23 (当月未过完，后续会继续增长)'
    rows.append((m, js[i], li[i], direct[i], total, rejected[i], expired[i], viewed[i],
                 partial, 'full-history-dashboard.html 月度数组（Gmail 检索核实，两次独立检索分别核实2025/2026部分后合并）', as_of))

conn.executemany("""INSERT INTO monthly_stats
    (month, js_submitted, li_submitted, direct_submitted, total_submitted, rejected, expired, viewed, partial, source, as_of_date)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)""", rows)

# ---------------------------------------------------------------
# 2) rejection_sample —— 来自"关于拒信原因"两张抽样表格，18行（19个月中25-06无样本，单列一行sample=0）
# 格式: (month, sample_size, with_feedback, cites_work_permit, is_exception, company, job_title, reason_detail, note)
# ---------------------------------------------------------------
sample_rows = [
    ('2025-03', 2, 2, 2, 0, None, None, None, None),
    ('2025-04', 7, 7, 6, 1, 'ENO International Trading Inc.', 'Data Analyst',
     '只写了担任 Data Analyst 年资、SQL 经验年资、担任 Risk Control Analyst 年资不够，完全没提工作权限', None),
    ('2025-05', 2, 2, 2, 0, None, None, None, None),
    ('2025-06', 0, 0, 0, 0, None, None, None, '当月没查到任何 JobStreet 拒信记录'),
    ('2025-07', 3, 3, 3, 0, None, None, None, None),
    ('2025-08', 1, 1, 1, 0, None, None, None, None),
    ('2025-09', 5, 4, 3, 1, 'Kian Ho Pte Ltd', 'Accounts & Operations Analyst',
     '只写资历类型不匹配，没提工作权限', None),
    ('2025-10', 5, 4, 3, 1, 'Sanmina-SCI Systems', 'Product Costing Analyst',
     '写资历类型、该岗位年资、RDBMS 经验、预测经验都不匹配，工作权限只字未提', None),
    ('2025-11', 5, 5, 5, 0, None, None, None, None),
    ('2025-12', 5, 5, 5, 0, None, None, None, None),
    ('2026-01', 5, 5, 4, 1, 'Genie Financial Services', 'Credit Analyst',
     '写相关岗位年资和期望月薪不匹配，没提工作权限', None),
    ('2026-02', 5, 4, 4, 0, None, None, None, None),
    ('2026-03', 5, 4, 4, 0, None, None, None, None),
    ('2026-04', 5, 4, 3, 1, 'Unity Assurance PAC', 'Accounts Executive',
     '写资历类型和期望月薪不匹配，没提工作权限', None),
    ('2026-05', 5, 5, 5, 0, None, None, None, None),
    ('2026-06', 5, 5, 5, 0, None, None, None, None),
    ('2026-07', 5, 5, 5, 0, None, None, None, None),
    ('2026-08', 5, 5, 5, 0, None, None, None, None),
]
conn.executemany("""INSERT INTO rejection_sample
    (month, sample_size, with_feedback, cites_work_permit, is_exception, company, job_title, reason_detail, note)
    VALUES (?,?,?,?,?,?,?,?,?)""", sample_rows)

# ---------------------------------------------------------------
# 3) companies —— 只收录已经核实研究过的公司（上一轮中文名核实调研 + milestone 提到的公司）
# size_basis 诚实记录判断依据，都是"没查到中文品牌/公开资料"这类弱证据，不是工商注册数据
# ---------------------------------------------------------------
company_rows = [
    ('ENO International Trading Inc.', None, 0, '贸易', 'sme_local_private',
     '未查到官方/常用中文名或公开品牌资料，按新加坡本地小型贸易公司处理', 'Data Analyst', '2025-04 拒信例外：反馈未提工作权限'),
    ('Kian Ho Pte Ltd', None, 0, '未知（本地私营）', 'sme_local_private',
     '未查到官方/常用中文名或公开品牌资料', 'Accounts & Operations Analyst', '2025-09 拒信例外：反馈未提工作权限'),
    ('Sanmina-SCI Systems', '新美亚（未核实，来源较弱，未采用）', 0, '电子制造服务（EMS）', 'large_mnc_or_soe',
     'Sanmina Corporation 为 NASDAQ 上市跨国电子制造服务企业，属于大型跨国公司；中文名来源不够可靠，未采用', 'Product Costing Analyst', '2025-10 拒信例外：反馈未提工作权限，是5个例外里唯一的大型跨国公司'),
    ('Genie Financial Services', None, 0, '金融服务', 'sme_local_private',
     '未查到官方/常用中文名或公开品牌资料，按新加坡本地小型金融服务公司处理', 'Credit Analyst', '2026-01 拒信例外：反馈未提工作权限'),
    ('Unity Assurance PAC', None, 0, '会计/审计（PAC=Public Accounting Corporation）', 'sme_local_private',
     '未查到官方/常用中文名或公开品牌资料，PAC 后缀通常指小型会计师事务所', 'Accounts Executive', '2026-04 拒信例外：反馈未提工作权限'),
    ('CHEC (China Harbour Engineering)', '中国港湾工程有限责任公司', 1, '工程建筑（央企）', 'large_mnc_or_soe',
     '中国交通建设集团下属央企，官方中文名可靠核实', 'Digitalisation Engineer', '2026-05 获得面试邀约'),
    ('LMS Group', None, 0, '物流贸易', 'sme_local_private',
     '新加坡本地私营物流贸易公司，未查到中文品牌资料', 'Inventory Analyst', '2025-10 获得面试邀约'),
    ('Kingstream Investment Holdings', None, 0, '大宗商品交易/投资控股', 'mid_size',
     'Suntec Tower Three 办公，规模判断依据有限', 'Trading Operations Executive', '2026-09 获得面试邀约'),
    ('IWC Management', None, 0, '基金管理（MAS持牌）', 'sme_local_private',
     'MAS 持牌基金管理公司，通常团队规模较小', 'Finance & Compliance Executive', '2026-09 获得面试邀约'),
]
conn.executemany("""INSERT INTO companies
    (name, chinese_name, chinese_name_verified, sector, size_category, size_basis, role_seen, notes)
    VALUES (?,?,?,?,?,?,?,?)""", company_rows)

# ---------------------------------------------------------------
# 4) applications —— 当前在跟进的投递（来自 memory /areas 摘要描述，2026-09 前后）
# 这层数据不是"拒信原因"分析的一部分，是为未来分析积累的公司/行业底表
# ---------------------------------------------------------------
active_apps = [
    ('1FSS Pte Ltd', 'Assistant Executive, Accounts Payable', '公共医疗财务共享服务', 'JobStreet', 'Screened', '2026-09-22', '/areas/1fss-accounts-payable.md', 'Bukit Merah, hybrid'),
    ('AAC Technologies', 'Sales & Operations Planner', '精密制造', 'JobStreet', 'Pursuing', '2026-09-19', '/areas/aac-technologies-salesopsplanner.md', 'Tampines'),
    ('Car Sales Executive (Kampong Ubi)', 'Car Sales Executive', '汽车经销', 'JobStreet', 'Pursuing', '2026-09-19', '/areas/car-sales-executive-kampongubi.md', 'Private Advertiser，公司未公开'),
    ('Centrum Solutions', 'Finance Executive', '多式联运物流/货运代理', 'JobStreet', 'Pursuing', '2026-09-17', '/areas/centrum-solutions-financeexec.md', None),
    ('Cushman & Wakefield', 'Finance Operations/Business Finance', '商业地产服务', 'LinkedIn', 'Applied', '2026-09-17', '/areas/cushman-wakefield-financeops.md', None),
    ('Ding Yue Pte Ltd', 'Senior Bullion Operations Executive', '贵金属/金条业务', 'JobStreet', 'Pursuing', '2026-09-23', '/areas/dingyue-bullionops.md', 'JobStreet 94820986'),
    ('DP Chemicals', 'Sales Executive', '化工贸易', 'JobStreet', 'Pursuing', '2026-09-19', '/areas/dp-chemicals-salesexec.md', 'East Region'),
    ('Fenergo', 'Enterprise Business Development Representative', 'RegTech/金融犯罪合规SaaS', 'LinkedIn', 'Pursuing', '2026-09-19', '/areas/fenergo-enterprise-bdr.md', '都柏林总部'),
    ('Four Points by Sheraton (Riverview)', 'Accounts Executive (Accounts Payable)', '酒店财务', 'JobStreet', 'Pursuing', '2026-09-24', '/areas/fourpoints-ap-executive.md', 'River Valley, JobStreet 94834928'),
    ('FOZL Group', 'Client Relationship Executive', '国际会计与咨询/公司服务', 'JobStreet', 'Pursuing', '2026-09-19', '/areas/fozl-group-clientrelationshipexec.md', 'Raffles Place'),
    ('Goodland Investments (Goodland Group)', 'Junior Accounts Executive', '投资/地产', '直投邮件', 'Pursuing', '2026-09-24', '/areas/goodland-junioraccounts.md', 'Kim Chuan Lane, MCF-2026-1679847'),
    ('HAC Commodities', 'Finance Executive', '大宗商品交易', 'JobStreet', 'Applying', '2026-09-17', '/areas/hac-commodities-financeexec.md', None),
    ('House of Amber Nectar', 'Junior Executive (AI & IT Operations)', '烈酒蒸馏/批发', 'JobStreet', 'Screened then dropped', '2026-09-22', '/areas/house-of-amber-nectar-juniorexecutive.md', 'Tuas'),
    ('HOYA Vision Care / HOYA Medical Singapore', 'Sales Support Executive', '医疗光学', 'JobStreet', 'Pursuing', '2026-09-22', '/areas/hoya-sales-support-executive.md', 'Job ID 2815, Toa Payoh'),
    ('HP Inc.', 'Business Analyst (Data & Information Technology)', '科技/硬件', 'LinkedIn', 'Pursuing', '2026-09-17', '/areas/hp-business-analyst.md', None),
    ('IBM Consulting', 'Associate Package Consultant, EA Business Transformation & Change', 'IT咨询', 'LinkedIn', 'Pursuing', '2026-09-22', '/areas/ibm-associate-package-consultant.md', 'Job ID 132755, entry level, hybrid'),
    ('IWC Management', 'Finance & Compliance Executive', '基金管理（MAS持牌）', 'JobStreet', 'Pursuing', '2026-09-23', '/areas/iwc-management.md', None),
    ('Kingstream Investment Holdings', 'Trading Operations Executive', '大宗商品交易/投资控股', 'JobStreet', 'Pursuing', '2026-09-22', '/areas/kingstream-tradingopsexec.md', 'Suntec Tower Three'),
    ('K.U.S Holdings (S) Pte Ltd', 'Group Procurement Executive', '采购', 'JobStreet', 'Pursuing', '2026-09-24', '/areas/kus-group-procurement.md', 'Sembawang/Senoko, JobStreet 94848058'),
    ('Linkwave Technologies / Linkwave AI', 'Sales Executive (eSIM)', '通信/eSIM', 'JobStreet', 'Pursuing', '2026-09-24', '/areas/linkwave-sales-executive.md', 'Clarke Quay, JobStreet 94609284'),
    ('Lobb Heng Pte Ltd', 'Junior Analyst (commodities/FX trading support)', '大宗商品/外汇交易支持', '直投邮件', 'Pursuing', '2026-09-24', '/areas/lobbheng-junioranalyst.md', 'MBFC, MCF-2026-1662152'),
    ('Mapletree', 'Accountant, Financial Planning & Analysis', '房地产/REIT', 'LinkedIn', 'Pursuing', '2026-09-23', '/areas/mapletree-fpa.md', 'hybrid, LinkedIn job 4467849400'),
    ('Michael Page (unnamed FMCG client)', 'Financial Analyst (APAC controlling)', '快消品', '猎头 recruiter', 'Applying', '2026-09-23', '/areas/michaelpage-fmcg-financialanalyst.md', 'consultant Elise Tok, JN-092026-7106777'),
    ('Nanhua Singapore', 'Settlements Analyst', '期货/证券经纪', 'JobStreet', 'Applying', '2026-09-17', '/areas/nanhua-settlements.md', None),
    ('OneCart', 'Sales Development Representative', 'B2B SaaS（电商库存/订单管理）', 'LinkedIn', 'Pursuing', '2026-09-17', '/areas/onecart-bd.md', None),
    ('PERSOL (unnamed financial-institution client)', 'Operations Officer (Structured Products)', '金融机构（结构性产品）', '猎头 recruiter', 'Pursuing', '2026-09-24', '/areas/persol-structured-products-ops.md', 'Bugis, JobStreet 94847831'),
    ('Prudential Assurance Singapore', 'Business Data Analyst', '保险', 'JobStreet', 'Pursuing', '2026-09-23', '/areas/prudential-businessdataanalyst.md', 'entry level, JobStreet 94829427, Gan Chye Keng'),
    ('Quess (after-sales/spare parts MNC)', 'Business Strategy Planning Executive', '售后/备件（MNC）', '猎头 recruiter', 'Pursuing', '2026-09-23', '/areas/quess-business-strategy-planning.md', 'East Singapore, recruiter John Koh'),
    ('Singapore Manufacturing Federation', 'Executive, Project Coordinator (Secretariat)', '行业标准组织', 'JobStreet', 'Pursuing', '2026-09-24', '/areas/smf-project-coordinator.md', 'Alexandra, JobStreet 94848645'),
    ('SMRT Corporation', 'Analyst, Strategy Enterprise Risk & Investment (SERI)', '公共交通', 'LinkedIn', 'Applying', '2026-09-17', '/areas/smrt-seri-analyst.md', None),
    ('Soleum Energy', 'Trade Finance Executive/Associate', '石油贸易', '直投邮件', 'Applied', '2026-09-24', '/areas/soleum-trade-finance.md', 'CBD'),
    ('Emplifi ("The Gift Expert")', 'Corporate Sales & Business Development Executive', '企业礼品/商品销售', 'JobStreet', 'Screened', '2026-09-22', '/areas/thegiftexpert-corporatesalesbd.md', None),
    ('TWG Tea Company', 'Accounts Assistant/Executive', '餐饮/零售茶饮', 'JobStreet', 'Pursuing', '2026-09-22', '/areas/twg-tea-accounts-assistant.md', 'Central Region'),
    ('UQPAY', 'Compliance Officer', '支付金融科技', 'JobStreet', 'Pursuing', '2026-09-24', '/areas/uqpay-compliance-officer.md', 'North Region, JobStreet 94831679'),
    ('Woodlands Sales Admin Assistant (undisclosed)', 'Sales Admin Assistant', '未知（本地）', 'JobStreet', 'Pursuing', '2026-09-19', '/areas/woodlands-salesadmin.md', 'Private Advertiser, North Region'),
    ('Yonyou Singapore', 'Business Development Executive', '企业软件/ERP', 'JobStreet', 'Pursuing', '2026-09-03', '/areas/yonyou-bd.md', None),
]

# 【2026-09-24 更正】上面列表里的 channel 有一部分是构建时推断的，memory 描述里并没有写渠道。
# 只保留描述里有明确证据的渠道（JobStreet编号 / LinkedIn job编号 / 写明email / 写明recruiter），
# 其余一律改为 'unknown'，不猜。channel_evidence 记录依据。
CHANNEL_EVIDENCE = {
    'Ding Yue Pte Ltd': ('JobStreet', '描述含 JobStreet 94820986'),
    'Four Points by Sheraton (Riverview)': ('JobStreet', '描述含 JobStreet 94834928'),
    'K.U.S Holdings (S) Pte Ltd': ('JobStreet', '描述含 JobStreet 94848058'),
    'Linkwave Technologies / Linkwave AI': ('JobStreet', '描述含 JobStreet 94609284'),
    'Prudential Assurance Singapore': ('JobStreet', '描述含 JobStreet 94829427'),
    'Singapore Manufacturing Federation': ('JobStreet', '描述含 JobStreet 94848645'),
    'UQPAY': ('JobStreet', '描述含 JobStreet 94831679'),
    'Mapletree': ('LinkedIn', '描述含 LinkedIn job 4467849400'),
    'Goodland Investments (Goodland Group)': ('直投邮件', '描述写明 applying by email'),
    'Lobb Heng Pte Ltd': ('直投邮件', '描述写明 applying by email'),
    'Soleum Energy': ('直投邮件', '描述写明 applied via email'),
    'Michael Page (unnamed FMCG client)': ('猎头 recruiter', '描述写明 via Michael Page consultant'),
    'Quess (after-sales/spare parts MNC)': ('猎头 recruiter', '描述写明 via Quess recruiter'),
    'PERSOL (unnamed financial-institution client)': ('猎头 recruiter', '描述写明 via recruiter PERSOL（岗位挂在 JobStreet 94847831）'),
}
SECTOR_FIX = {'K.U.S Holdings (S) Pte Ltd': '未知（"采购"是岗位职能，不是行业）'}

fixed_apps = []
for row in active_apps:
    company, title, sector, _channel, status, sdate, mfile, notes = row
    ch, ev = CHANNEL_EVIDENCE.get(company, ('unknown', 'memory 描述未写渠道，不推断'))
    sector = SECTOR_FIX.get(company, sector)
    fixed_apps.append((company, title, sector, ch, ev, status, sdate, mfile, notes))

conn.executemany("""INSERT INTO applications
    (company, job_title_en, sector, channel, channel_evidence, status, status_date, memory_file, notes)
    VALUES (?,?,?,?,?,?,?,?,?)""", fixed_apps)

# ---------------------------------------------------------------
# 5) meta —— 记录数据核实到什么时间点，供增量更新脚本判断从哪天开始查新邮件
# ---------------------------------------------------------------
meta_rows = [
    ('monthly_stats_as_of', '2026-09-23'),
    ('rejection_sample_as_of', '2026-08-31 (2026-09单独全量核查，未纳入此抽样表)'),
    ('applications_snapshot_as_of', '2026-09-24'),
    ('db_built_date', '2026-09-24'),
    ('db_build_note', '所有数据来自已核实的看板/抽样/memory记录，本次构建未重新扫描Gmail全量邮件'),
    ('fix_2026-09-24_channel', 'applications.channel 原先部分为推断值，已改为只保留有明确证据的渠道，其余为 unknown'),
    ('flag_expired_exceeds_js', '累计过期通知(964) > 累计JobStreet投递(912)，2025-05时已是41 vs 28；过期数不能全部解读为"我投的岗位没回音"，可能含收藏未投的岗位，或JobStreet投递数有漏计，需邮件层面核实'),
    ('applications_sector_note', 'applications.sector 部分为常识性行业标签（如 Mapletree=房地产），非来自 memory 描述原文'),
]
conn.executemany("INSERT INTO meta (key, value) VALUES (?,?)", meta_rows)

conn.commit()

# 简单校验
cur = conn.cursor()
for t in ['monthly_stats', 'rejection_sample', 'companies', 'applications', 'meta']:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"{t}: {cur.fetchone()[0]} 行")

conn.close()
print(f"\n数据库已生成：{DB_PATH}")
