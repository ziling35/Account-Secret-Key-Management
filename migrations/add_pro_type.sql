-- Pro类型支持 - 数据库迁移SQL
-- 执行时间: 2024-12
-- 功能: 添加Pro卡密类型和Pro账号字段

-- 1. 为 accounts 表添加 is_pro 字段
-- SQLite 不支持 IF NOT EXISTS 语法用于 ALTER TABLE
-- 如果字段已存在会报错，可以忽略

ALTER TABLE accounts ADD COLUMN is_pro BOOLEAN DEFAULT FALSE NOT NULL;

-- 2. 为 is_pro 字段创建索引（加速Pro账号查询）
CREATE INDEX IF NOT EXISTS ix_accounts_is_pro ON accounts (is_pro);

-- 注意：
-- - key_type 字段已经是 VARCHAR 类型，可以直接存储 'pro' 值
-- - 如果使用的是 SQLite，枚举值是作为字符串存储的
-- - 执行后可以：
--   1. 在后台创建 'pro' 类型卡密
--   2. 上传账号时标记为Pro账号
--   3. Pro卡密只能获取Pro账号
--   4. Pro账号用户无需安装插件
