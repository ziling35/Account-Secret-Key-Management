-- ============================================================
-- 团队成员管理数据库迁移 SQL
-- 用于固定Pro账号积分检测与自动切换功能
-- ============================================================

-- 0. 给 keys 表添加 team_id 字段（关联团队）
ALTER TABLE keys ADD COLUMN IF NOT EXISTS team_id INTEGER;

-- 0.1 如果 team_configs 表已存在，移除 key_code 的 NOT NULL 约束
-- 注意：如果表已存在且有 key_code 字段，需要先修改约束
DO $$
BEGIN
    -- 检查表是否存在
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'team_configs') THEN
        -- 检查 key_code 列是否存在
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'team_configs' AND column_name = 'key_code') THEN
            -- 将 key_code 改为可空
            ALTER TABLE team_configs ALTER COLUMN key_code DROP NOT NULL;
        END IF;
    END IF;
END $$;

-- 0.2 移除 member_switch_history 表的 key_code NOT NULL 约束
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'member_switch_history' AND column_name = 'key_code') THEN
        ALTER TABLE member_switch_history ALTER COLUMN key_code DROP NOT NULL;
    END IF;
END $$;

-- 0.3 添加 team_members.is_exhausted 列（标记积分已用尽的成员）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'team_members' AND column_name = 'is_exhausted') THEN
        ALTER TABLE team_members ADD COLUMN is_exhausted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;
END $$;

-- ============================================================

-- 1. 创建 team_configs 表（团队配置）
-- 注意：多个卡密可关联到同一个团队（通过 keys.team_id）
CREATE TABLE IF NOT EXISTS team_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,                              -- 团队名称
    admin_email VARCHAR NOT NULL,                       -- 管理员邮箱
    admin_password VARCHAR NOT NULL,                    -- 管理员密码
    admin_api_key VARCHAR,                              -- 管理员API Key
    admin_token VARCHAR,                                -- 管理员Token（缓存）
    windsurf_team_id VARCHAR,                           -- Windsurf团队ID
    is_active BOOLEAN NOT NULL DEFAULT TRUE,            -- 是否启用
    credits_threshold INTEGER NOT NULL DEFAULT 20,      -- 积分阈值
    check_interval_minutes INTEGER NOT NULL DEFAULT 5,  -- 检测间隔（分钟）
    current_member_id INTEGER,                          -- 当前成员ID
    last_check_at TIMESTAMP,                            -- 最后检测时间
    last_switch_at TIMESTAMP,                           -- 最后切换时间
    switch_count INTEGER NOT NULL DEFAULT 0,            -- 切换次数
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- team_configs 索引
CREATE INDEX IF NOT EXISTS ix_team_configs_is_active ON team_configs(is_active);

-- ============================================================

-- 2. 创建 team_members 表（团队成员）
CREATE TABLE IF NOT EXISTS team_members (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL,                           -- 所属团队ID
    email VARCHAR NOT NULL,                             -- 成员邮箱
    password VARCHAR NOT NULL,                          -- 成员密码
    api_key VARCHAR,                                    -- 成员API Key（sk-ws-...）
    name VARCHAR,                                       -- 成员名称
    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,          -- 是否已启用
    is_current BOOLEAN NOT NULL DEFAULT FALSE,          -- 是否为当前成员
    last_credits INTEGER NOT NULL DEFAULT 0,            -- 最后积分
    last_check_at TIMESTAMP,                            -- 最后检测时间
    enabled_at TIMESTAMP,                               -- 启用时间
    disabled_at TIMESTAMP,                              -- 禁用时间
    sort_order INTEGER NOT NULL DEFAULT 0,              -- 排序
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- team_members 索引
CREATE INDEX IF NOT EXISTS ix_team_members_team_id ON team_members(team_id);
CREATE INDEX IF NOT EXISTS ix_team_members_email ON team_members(email);
CREATE INDEX IF NOT EXISTS ix_team_members_is_current ON team_members(is_current);

-- ============================================================

-- 3. 创建 member_switch_history 表（成员切换历史）
CREATE TABLE IF NOT EXISTS member_switch_history (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL,                           -- 团队ID
    from_member_id INTEGER,                             -- 原成员ID
    to_member_id INTEGER NOT NULL,                      -- 新成员ID
    from_email VARCHAR,                                 -- 原成员邮箱
    to_email VARCHAR NOT NULL,                          -- 新成员邮箱
    reason VARCHAR NOT NULL,                            -- 切换原因
    credits_before INTEGER,                             -- 切换前积分
    switched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP  -- 切换时间
);

-- member_switch_history 索引
CREATE INDEX IF NOT EXISTS ix_member_switch_history_team_id ON member_switch_history(team_id);

-- ============================================================
-- 迁移完成！
-- ============================================================
