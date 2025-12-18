-- 账号获取历史表 - 数据库迁移SQL (PostgreSQL)
-- 执行时间: 2024-12
-- 功能: 添加账号获取历史表，用于记录Pro卡密等可重复获取账号的历史

-- 创建 account_assignment_history 表
CREATE TABLE IF NOT EXISTS account_assignment_history (
    id SERIAL PRIMARY KEY,
    key_code VARCHAR NOT NULL,
    account_id INTEGER NOT NULL,
    email VARCHAR NOT NULL,
    password VARCHAR,
    api_key VARCHAR,
    name VARCHAR,
    is_pro BOOLEAN DEFAULT FALSE NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS ix_account_assignment_history_key_code ON account_assignment_history (key_code);
CREATE INDEX IF NOT EXISTS ix_account_assignment_history_account_id ON account_assignment_history (account_id);

-- 注意：
-- - 此表用于记录Pro卡密获取账号的历史
-- - Pro账号可以被多个密钥获取，所以需要单独的历史表
-- - 普通账号仍然使用 accounts 表的 assigned_to_key 字段
