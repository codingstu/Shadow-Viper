-- SpiderFlow 持久化框架 - Supabase 数据库初始化脚本
-- 执行此脚本以创建所有必要的表和索引
-- 这是 Plan A（完整持久化）的数据库基础设施

-- ==================== 表1: sources_cache ====================
-- 用途：缓存已爬取的订阅源原始内容，避免重复爬取
-- TTL：6小时自动过期
-- 容量：~1MB

CREATE TABLE IF NOT EXISTS sources_cache (
    id BIGSERIAL PRIMARY KEY,
    source_url TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,  -- Base64编码的源内容
    node_count INTEGER DEFAULT 0,
    last_fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ttl_hours INTEGER DEFAULT 6,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sources_cache_source_url ON sources_cache(source_url);
CREATE INDEX IF NOT EXISTS idx_sources_cache_last_fetched ON sources_cache(last_fetched_at);

-- RLS策略：允许所有操作（内部使用）
ALTER TABLE sources_cache ENABLE ROW LEVEL SECURITY;
CREATE POLICY "允许所有操作" ON sources_cache
    USING (true)
    WITH CHECK (true);

-- ==================== 表2: parsed_nodes ====================
-- 用途：缓存已解析的节点信息，避免重复解析
-- TTL：6小时自动过期
-- 容量：~15MB

CREATE TABLE IF NOT EXISTS parsed_nodes (
    id BIGSERIAL PRIMARY KEY,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    name TEXT,
    protocol TEXT,
    full_content JSONB,  -- 完整的节点配置信息
    source_url TEXT,
    parsed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '6 hours',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(host, port, protocol)
);

CREATE INDEX IF NOT EXISTS idx_parsed_nodes_host_port ON parsed_nodes(host, port);
CREATE INDEX IF NOT EXISTS idx_parsed_nodes_protocol ON parsed_nodes(protocol);
CREATE INDEX IF NOT EXISTS idx_parsed_nodes_expires_at ON parsed_nodes(expires_at);
CREATE INDEX IF NOT EXISTS idx_parsed_nodes_source_url ON parsed_nodes(source_url);

-- RLS策略：允许所有操作（内部使用）
ALTER TABLE parsed_nodes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "允许所有操作" ON parsed_nodes
    USING (true)
    WITH CHECK (true);

-- ==================== 表3: testing_queue ====================
-- 用途：记录测速任务的进度和状态，支持断点续测
-- 保留期：7天自动清理
-- 容量：~2MB

CREATE TABLE IF NOT EXISTS testing_queue (
    id BIGSERIAL PRIMARY KEY,
    group_number INTEGER NOT NULL,  -- 分组编号（0-9）
    group_position INTEGER NOT NULL,  -- 组内位置
    node_host TEXT NOT NULL,
    node_port INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'testing', 'passed', 'failed', 'timeout'
    attempted_count INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    result_data JSONB,  -- 测试结果的详细数据
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(node_host, node_port)
);

CREATE INDEX IF NOT EXISTS idx_testing_queue_status ON testing_queue(status);
CREATE INDEX IF NOT EXISTS idx_testing_queue_group ON testing_queue(group_number, group_position);
CREATE INDEX IF NOT EXISTS idx_testing_queue_node ON testing_queue(node_host, node_port);
CREATE INDEX IF NOT EXISTS idx_testing_queue_created_at ON testing_queue(created_at);

-- RLS策略：允许所有操作（内部使用）
ALTER TABLE testing_queue ENABLE ROW LEVEL SECURITY;
CREATE POLICY "允许所有操作" ON testing_queue
    USING (true)
    WITH CHECK (true);

-- ==================== 辅助函数：自动清理过期数据 ====================

-- 创建清理过期源缓存的函数
CREATE OR REPLACE FUNCTION cleanup_expired_sources()
RETURNS void AS $$
BEGIN
    DELETE FROM sources_cache
    WHERE last_fetched_at < NOW() - INTERVAL '1' DAY;
END;
$$ LANGUAGE plpgsql;

-- 创建清理过期节点缓存的函数
CREATE OR REPLACE FUNCTION cleanup_expired_nodes()
RETURNS void AS $$
BEGIN
    DELETE FROM parsed_nodes
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- 创建清理已完成任务的函数
CREATE OR REPLACE FUNCTION cleanup_completed_tasks()
RETURNS void AS $$
BEGIN
    DELETE FROM testing_queue
    WHERE created_at < NOW() - INTERVAL '7' DAY
    AND status IN ('passed', 'failed', 'timeout');
END;
$$ LANGUAGE plpgsql;

-- ==================== 验证脚本 ====================
-- 执行以下语句验证所有表已正确创建

-- 检查 sources_cache 表
-- SELECT COUNT(*) as sources_cache_rows FROM sources_cache;

-- 检查 parsed_nodes 表
-- SELECT COUNT(*) as parsed_nodes_rows FROM parsed_nodes;

-- 检查 testing_queue 表
-- SELECT COUNT(*) as testing_queue_rows FROM testing_queue;

-- ==================== 初始化完成 ====================
-- 这个脚本创建了：
-- ✅ 3个核心表（sources_cache, parsed_nodes, testing_queue）
-- ✅ 优化索引用于快速查询
-- ✅ RLS策略以支持安全访问
-- ✅ 辅助函数用于自动清理
--
-- 下一步：
-- 1. 在 Supabase SQL Editor 中复制此脚本
-- 2. 执行脚本以创建所有表
-- 3. 启动后端 Python 程序
-- 4. 观察日志确认"✅ 持久化表初始化完成"
-- 5. 开始爬虫：http://localhost:8000/nodes/scan
