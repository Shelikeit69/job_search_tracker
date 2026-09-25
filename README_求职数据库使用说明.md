# 求职投递追踪数据库 — 使用说明

版本：2026-09-25（第三版：新增逐条投递记录，更正第二版的拒信比例）

## 这是什么

`job_search_tracker.db` 是一个 SQLite 数据库，存了 2025年3月到2026年9月24日从 Gmail 提取的求职记录。第三版开始，每份投递、每封结果通知都单独存一行，并带 Gmail message id，可以回到原邮件核对。以后做分析先查这个库，只有新邮件才需要查 Gmail。

## 表结构

**逐条记录（第三版新增，以后以这两张表为准）**

1. **application_log**：每份投递一行，共2241行（JobStreet 1592、LinkedIn 615、直投邮件 34）。字段包括渠道、投递时间（新加坡时间）、公司、职位、最终结果、查看/拒信/过期/面试的时间、投递到拒信的天数、Gmail message id，以及 n_sources（这条记录在几轮独立提取里出现过，≥2 表示交叉核对过）。
2. **application_events**：每封结果通知一行，共2242行：JobStreet 拒信464、查看220、过期968（另有5封周报摘要），LinkedIn 拒信152、查看60，公司/猎头直接发的拒信88，邮件里的面试邀约17，公司官网/ATS 投递确认268。app_id 指向匹配到的投递，匹配不上为空。

结果（outcome）的判定顺序：有面试 → interview；有拒信 → rejected；JobStreet 帖子过期且没收到拒信 → expired_no_reply；只被查看过 → viewed_no_decision；什么都没收到 → no_response。

**旧表（保留作历史对照）**

3. **monthly_stats**：旧看板的月度汇总。JobStreet 投递严重少计（912，逐条实际是1592），原因是当时用搜索预览计数，JobStreet 把同一天的确认邮件合并成一个线程，预览只显示前5封。以 application_log 为准。
4. **rejection_sample**：75封拒信逐封读正文的抽样核查，93%标注工作权限不匹配。这张表和计数方式无关，结论仍然有效。
5. **companies**、**applications**：9家公司背景、36份重点跟进的投递，同第二版。
6. **meta**：数据日期、更正记录和已知问题，共13条。

## 模式分析结论（`python3 analysis.py` 可重跑）

以下比例按"投递批次"计算，即某个月投出去的申请最后收到了什么结果，不含还在进行中的2026年9月。

**1. JobStreet 上三分之二的投递没有任何回音，约三成收到拒信。** 1356份里，65.6%帖子过期都没有回复，29.6%被拒，只被查看、没下文的0.3%，获得面试的0.2%（3份）。LinkedIn 594份：67.0%没有回音，26.1%被拒，6.7%被查看后没下文，1份面试。

**2. JobStreet 大部分拒信发出前，雇主没有打开过你的申请。** 458封拒信里，352封（76.9%）之前没有收到过"雇主已查看"通知；从投递到收到拒信的中位数是2.9天。结合抽样里93%的拒信标注工作权限不匹配，最合理的解释是：大部分拒绝是 JobStreet 根据筛选问题的答案自动做出的，没有人看过简历。这是推断，"已查看"通知也可能有漏发的情况。

**3. 硕士毕业没有改变结果。** JobStreet 被拒比例毕业前28.1%、毕业后31.1%，被查看比例12.1%→14.9%，过期无回音66.4%→64.9%，变化都不大。

**4. 面试邀约主要不是来自 JobStreet 和 LinkedIn 一键投递。** 邮件里能查到17次面试邀约，来自15家雇主：JobStreet 3家（CHEC、Ola Party、Absolute Kinetics），LinkedIn 1家（Belden，是招聘人员主动发 InMail），直投邮件1家（IWC），公司官网/ATS 3家（Qualcomm、YipitData、STX），另外7家在邮件里找不到对应的投递记录（LMS Group、Fuku、Tapestry、Instron/ITW、HOPA、OneCart、Kingstream），可能来自猎头、内推、InternSG 或平台外的联系。JobStreet 和 LinkedIn 占了已记录投递的98%，但只贡献了15家里的4家。样本小，而且你说过很多面试是电话或 WhatsApp 约的，不在邮件里，所以这只能算方向性的信号。

## 对第二版结论的更正

- 第二版说"每投100份 JobStreet，约58份被拒"，这是错的。分母用的是少计的月度投递数（912），实际约三成被拒。拒信数和投递量高度相关这一点方向没变，但具体比例作废。
- 第二版提出的"过期通知数(964)比投递数(912)多"的疑问已经解开：投递数少计了，逐条统计的 JobStreet 投递是1592份，过期968条。
- 旧看板和给父母的 PDF 里的数字（累计投递1726、拒信524、面试4次）都基于旧的少计数据，需要更新。

## 已知限制

- **LinkedIn 投递大多没有职位名。** 确认邮件标题里只有公司名；有 LinkedIn 拒信的，职位从拒信标题里补上了。
- **公司官网/ATS 投递还没计入。** 268封确认邮件（Workday、Greenhouse、SmartRecruiters 等）里有重复和提醒，要逐封清洗后才能变成投递记录，所以真实投递总数比2241多，估计多两百份左右。
- **直投渠道的拒信和面试可信度低一些。** 这些是模型从邮件内容判断出来的，并按公司名模糊匹配（只匹配60天内的投递）。88封直接拒信里只有16封能对上已记录的投递，其余大多来自官网投递。
- **电话、WhatsApp 约的面试不在数据里。**
- 随机抽查的9条记录（JobStreet 投递、LinkedIn 投递、JobStreet 拒信/过期/查看、LinkedIn 拒信、公司直接拒信）和一个33封的按天合并线程，都和 Gmail 原邮件一致；994份 JobStreet 投递在两轮独立提取里都出现过。

## 以后怎么更新

1. 查 `meta` 表里的 `application_log_as_of`，只提取这个日期之后的新邮件，按 raw 文件夹里现有的格式存成新的 `.jsonl` 放进 `raw/`。
2. 依次运行：`python3 build_db.py`、`python3 merge_raw.py`、`python3 build_log.py`、`python3 analysis.py`。merge_raw.py 会按 message id 自动去重。
3. `raw_extracts.zip` 解压后就是 `raw/` 文件夹，重跑 merge_raw.py 必须要有它。

## 文件清单

- `job_search_tracker.db`：数据库本体
- `applications_all.jsonl`、`events_all.jsonl`：合并后的逐条记录（纯文本，GitHub 上可以直接看）
- `raw_extracts.zip`：各轮 Gmail 提取的原始记录
- `merge_raw.py`：合并、去重、解析公司和职位
- `build_log.py`：写入逐条表并把结果匹配回投递
- `build_db.py`、`schema.sql`：建旧表（第二版）
- `analysis.py`：模式分析
- `query_examples.sql`：常用查询
- 本说明文件
