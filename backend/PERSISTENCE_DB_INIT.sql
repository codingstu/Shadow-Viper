-- Supabase SQL 初始化脚本
-- 用于创建 SpiderFlow 持久化所需的三个表
-- 
-- 使用方法：
-- 1. 打开 Supabase 控制面板
-- 2. 进入 SQL Editor
-- 3. 复制以下 SQL 并执行
-- 4. 后端会自动识别这些表

-- ==================== 表1: sources_cache ====================
-- 用途：缓存订阅源的原始爬取内容
-- TTL：6 小时

CREATE TABLE IF NOT EXISTS public.sources_cache (
    id BIGINT PRIMARY KEY,
    source_url VARCHAR(500) UNIQUE NOT NULL,
    content TEXT NOT NULL,                      -- base64 编码的爬取内容
    node_count INT DEFAULT 0,                   -- 该源的节点数
    last_fetched_at TIMESTAMP WITH TIME ZONE,   -- 上次爬取时间
    ttl_hours INT DEFAULT 6,                    -- 缓存有效期（小时）
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引以加快查询
CREATE INDEX IF NOT EXISTS idx_sources_cache_url ON public.sources_cache(source_url);
CREATE INDEX IF NOT EXISTS idx_sources_cache_fetched ON public.sources_cache(last_fetched_at);

-- 启用行级安全性 (RLS)
ALTER TABLE public.sources_cache ENABLE ROW LEVEL SECURITY;

-- 创建策略：允许所有用户读写
CREATE POLICY "Allow all operations on sources_cache"
    ON public.sources_cache
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ==================== 表2: parsed_nodes ====================
-- 用途：缓存解析后的节点数据
-- TTL：6 小时
-- 主要用于快速恢复和避免重复解析

CREATE TABLE IF NOT EXISTS public.parsed_nodes (
    id BIGINT PRIMARY KEY,
    host VARCHAR(255) NOT NULL,
    port INT NOT NULL,
    name VARCHAR(255),
    protocol VARCHAR(50),                       -- vmess, vless, trojan, hysteria 等
    full_content TEXT NOT NULL,                 -- JSON 格式的完整节点数据
    source_url VARCHAR(500),                    -- 来自哪个订阅源
    parsed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(host, port)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_parsed_nodes_host_port ON public.parsed_nodes(host, port);
CREATE INDEX IF NOT EXISTS idx_parsed_nodes_updated ON public.parsed_nodes(updated_at);
CREATE INDEX IF NOT EXISTS idx_parsed_nodes_source ON public.parsed_nodes(source_url);

-- 启用 RLS
ALTER TABLE public.parsed_nodes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all operations on parsed_nodes"
    ON public.parsed_nodes
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ==================== 表3: testing_queue ====================
-- 用途：记录测速任务队列和进度
-- 用于支持重启恢复和测速进度持久化
-- 主要字段：
--   - group_number: 测速分组编号 (1-20)
--   - group_position: 组内位置 (1-50)
--   - status: pending (待测) / testing (测试中) / completed (已完成) / failed (失败)
--   - attempted_count: 失败重试次数

CREATE TABLE IF NOT EXISTS public.testing_queue (
    id BIGINT PRIMARY KEY,
    group_number INT NOT NULL,                  -- 第几组 (1-20)
    group_position INT NOT NULL,                -- 组内第几个 (1-50)
    node_host VARCHAR(255) NOT NULL,
    node_port INT NOT NULL,
    node_name VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',       -- pending, testing, completed, failed
    attempted_count INT DEFAULT 0,              -- 尝试次数
    last_tested_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_testing_queue_status ON public.testing_queue(status);
CREATE INDEX IF NOT EXISTS idx_testing_queue_group ON public.testing_queue(group_number, group_position);
CREATE INDEX IF NOT EXISTS idx_testing_queue_node ON public.testing_queue(node_host, node_port);

-- 启用 RLS
ALTER TABLE public.testing_queue ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all operations on testing_queue"
    ON public.testing_queue
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ==================== 快速清理操作 ====================
-- 如果需要重新初始化，可以使用以下命令清空表：
--
-- DELETE FROM public.sources_cache;
-- DELETE FROM public.parsed_nodes;
-- DELETE FROM public.testing_queue;
--
-- 然后后端会自动重新爬取和解析。

-- ==================== 监控和统计 ====================
-- 查看各个表的大小和数量

-- 查看缓存统计
-- SELECT 
--   'sources_cache' as table_name, COUNT(*) as record_count
-- FROM public.sources_cache
-- UNION ALL
-- SELECT 
--   'parsed_nodes', COUNT(*)
-- FROM public.parsed_nodes
-- UNION ALL
-- SELECT 
--   'testing_queue', COUNT(*)
-- FROM public.testing_queue;

-- 查看测速进度
-- SELECT 
--   group_number,
--   COUNT(*) as total,
--   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
--   SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
--   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
-- FROM public.testing_queue
-- GROUP BY group_number
-- ORDER BY group_number;
