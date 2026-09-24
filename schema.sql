-- Toni 求职投递追踪数据库
-- 设计目的：把已经核实过的数据固化下来，后续新的分析需求先查这个库，
-- 只在库里没有的数据缺口上才去查 Gmail（增量更新），不再每次都全量翻邮箱。

-- 每月汇总统计：投递量（按渠道）+ 收到的结果（按类型）
-- 来源：full-history-dashboard.html 中已核实的月度数组（2026-09-23 版本生成）
CREATE TABLE IF NOT EXISTS monthly_stats (
  month TEXT PRIMARY KEY,          -- 'YYYY-MM'，26-09 为不完整月份（截至09-23，标 partial=1）
  js_submitted INTEGER,            -- JobStreet 投递数
  li_submitted INTEGER,            -- LinkedIn 投递数
  direct_submitted INTEGER,        -- 直投邮件数
  total_submitted INTEGER,         -- 三者之和
  rejected INTEGER,                -- 当月收到的明确拒信数
  expired INTEGER,                 -- 当月收到的帖子过期通知数
  viewed INTEGER,                  -- 当月收到的"雇主查看/已浏览"通知数
  partial INTEGER DEFAULT 0,       -- 1 = 当月未过完，数字会继续增长
  source TEXT,                     -- 数据来源说明
  as_of_date TEXT                  -- 这行数字核实到哪一天
);

-- 拒信原因抽样核查记录：每月抽样 ~5 封 JobStreet 带反馈详情的拒信，逐封读正文核实
-- 来源：full-history-dashboard.html "关于拒信原因" 抽样表格（2025-03 至 2026-08，共18个月）
CREATE TABLE IF NOT EXISTS rejection_sample (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  month TEXT,
  sample_size INTEGER,             -- 当月抽样打开的邮件数
  with_feedback INTEGER,           -- 其中带具体反馈详情的数量
  cites_work_permit INTEGER,       -- 其中标注"工作权限不匹配"的数量
  is_exception INTEGER DEFAULT 0,  -- 1 = 该月存在"未提工作权限"的例外案例（下面company/reason记录例外详情）
  company TEXT,                    -- 例外案例的公司名（非例外月份为空）
  job_title TEXT,                  -- 例外案例的职位名
  reason_detail TEXT,              -- 例外案例拒信里实际写的理由
  note TEXT
);

-- 公司背景库：只收录已经过核实研究的公司（中文名核实 / 行业 / 规模判断），
-- 避免每次分析都重新去查同一家公司。size_basis 诚实记录判断依据，不是精确雇员数。
CREATE TABLE IF NOT EXISTS companies (
  name TEXT PRIMARY KEY,           -- 英文公司名（作为唯一键）
  chinese_name TEXT,               -- 核实过的官方/常用中文名，没有就留空，不能瞎猜
  chinese_name_verified INTEGER DEFAULT 0,  -- 1 = 有可靠来源核实过
  sector TEXT,                     -- 行业大类
  size_category TEXT,              -- 'large_mnc_or_soe' / 'sme_local_private' / 'mid_size' / 'unknown'
  size_basis TEXT,                 -- 判断依据（诚实注明，比如"无法查到中文品牌/公开资料"）
  role_seen TEXT,                  -- 关联到的岗位名称（可能有多个，逗号分隔）
  notes TEXT
);

-- 当前活跃投递记录（2026-09 前后，来自 Obsidian/memory /areas 追踪文件的摘要）
-- 这一层是"正在跟进中"的申请，用于后续做行业/规模 vs 结果 的模式分析
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company TEXT,
  job_title_en TEXT,
  sector TEXT,
  channel TEXT,                    -- JobStreet / LinkedIn / 直投邮件 / 猎头 recruiter / unknown（没有证据就填 unknown，不猜）
  channel_evidence TEXT,           -- 渠道判断依据
  status TEXT,                     -- Pursuing / Screened / Applied / Applying / Dropped
  status_date TEXT,                -- 记录最后更新日期
  memory_file TEXT,                -- 对应的 memory /areas 文件路径（便于追溯）
  notes TEXT
);

-- 数据库元信息：记录每张表的数据核实到什么时间点，方便增量更新时知道从哪天开始查新邮件
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
