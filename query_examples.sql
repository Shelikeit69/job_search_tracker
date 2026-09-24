-- 常用查询示例，用 sqlite3 job_search_tracker.db 打开后直接跑，
-- 或者以后新开对话时让 Claude 先跑这几条，而不是重新翻 Gmail。

-- 1. 累计投递/结果总数（对应看板顶部的5个数字）
SELECT SUM(total_submitted) AS 累计投递,
       SUM(rejected) AS 累计拒信,
       SUM(expired) AS 累计过期,
       SUM(viewed) AS 累计查看待定
FROM monthly_stats;

-- 2. 某个月的投递/结果明细
SELECT * FROM monthly_stats WHERE month = '2026-08';

-- 3. 拒信原因抽样：总体 work-permit 引用率
SELECT SUM(with_feedback) AS 有反馈详情合计,
       SUM(cites_work_permit) AS 标注工作权限合计,
       ROUND(100.0 * SUM(cites_work_permit) / SUM(with_feedback), 1) AS 占比百分比
FROM rejection_sample;

-- 4. 所有"未提工作权限"的例外案例，附公司背景
SELECT r.month, r.company, r.job_title, r.reason_detail, c.sector, c.size_category
FROM rejection_sample r LEFT JOIN companies c ON r.company = c.name
WHERE r.is_exception = 1;

-- 5. 当前在跟进的投递，按行业统计数量
SELECT sector, COUNT(*) AS 数量 FROM applications GROUP BY sector ORDER BY 数量 DESC;

-- 6. 当前在跟进的投递，按渠道统计数量
SELECT channel, COUNT(*) AS 数量 FROM applications GROUP BY channel ORDER BY 数量 DESC;

-- 7. 查数据核实到哪一天（增量更新前先看这个，决定从哪天开始查新邮件）
SELECT * FROM meta;
