-- 常用查询示例（第四版，数据截至 2026-10-01）。以 application_log / application_events 为准，
-- monthly_stats 是旧看板的汇总，JobStreet 少计，只留作历史对照。

-- 1. 各渠道投递数
SELECT channel, COUNT(*) FROM application_log GROUP BY channel;

-- 2. 每月投递数（按渠道）
SELECT applied_month,
       SUM(channel='JobStreet') AS JobStreet, SUM(channel='LinkedIn') AS LinkedIn,
       SUM(channel='直投邮件') AS 直投, COUNT(*) AS 合计
FROM application_log GROUP BY applied_month ORDER BY applied_month;

-- 3. 每份投递的最终结果分布（按渠道）
SELECT channel, outcome, COUNT(*) FROM application_log GROUP BY channel, outcome ORDER BY channel, 3 DESC;

-- 4. 查某家公司的全部投递和结果
SELECT applied_at, channel, company, job_title, outcome, viewed_at, rejected_at, expired_at
FROM application_log WHERE lower(company) LIKE '%mapletree%';

-- 5. 某份投递收到过哪些通知
SELECT event_at, type, subject FROM application_events WHERE app_id = 1605 ORDER BY event_at;

-- 6. 全部面试邀约及匹配到的投递
SELECT e.event_at, e.company, e.job_title, a.channel, a.applied_at
FROM application_events e LEFT JOIN application_log a ON a.app_id = e.app_id
WHERE e.type = 'interview' ORDER BY e.event_at;

-- 7. JobStreet 拒信前雇主是否打开过
SELECT SUM(viewed_at IS NOT NULL AND viewed_at <= rejected_at) AS 看过再拒,
       SUM(viewed_at IS NULL OR viewed_at > rejected_at) AS 没看就拒
FROM application_log WHERE channel = 'JobStreet' AND rejected_at IS NOT NULL;

-- 8. 数据核实到哪一天、有哪些已知问题
SELECT * FROM meta;

-- 9. 某一天的投递明细（新加坡时间），代替单独的每日表格
SELECT substr(applied_at, 12, 5) AS 时间, channel, company, job_title, outcome
FROM application_log WHERE applied_at LIKE '2026-10-01%' ORDER BY applied_at;
