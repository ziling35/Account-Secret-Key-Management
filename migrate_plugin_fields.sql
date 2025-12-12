-- =====================================================
-- 插件信息表字段扩展 SQL 脚本
-- 添加客户端展示所需的所有字段
-- 可直接在 PostgreSQL 中执行
-- =====================================================

-- 添加客户端展示字段到 plugin_info 表
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS ide_type VARCHAR(50) DEFAULT 'windsurf';
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS icon VARCHAR(50) DEFAULT 'shield-check';
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS icon_gradient JSON;
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS features JSON;
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS usage_steps JSON;
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS tips JSON;
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS mcp_config_path VARCHAR(255);
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS extensions_path VARCHAR(255);
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS mcp_extra_config JSON;
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS is_primary BOOLEAN DEFAULT FALSE;
ALTER TABLE plugin_info ADD COLUMN IF NOT EXISTS sort_order INT DEFAULT 0;

-- 修改现有字段类型为 TEXT（支持更长内容）
ALTER TABLE plugin_info ALTER COLUMN changelog TYPE TEXT;
ALTER TABLE plugin_info ALTER COLUMN update_description TYPE TEXT;

-- 添加 plugin_name 唯一约束（如果不存在）
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'plugin_info_plugin_name_key'
    ) THEN
        ALTER TABLE plugin_info ADD CONSTRAINT plugin_info_plugin_name_key UNIQUE (plugin_name);
    END IF;
END $$;

-- 创建 ide_type 索引（提高查询性能）
CREATE INDEX IF NOT EXISTS ix_plugin_info_ide_type ON plugin_info (ide_type);

-- 显示迁移结果
SELECT 
    'Migration completed successfully!' as status,
    COUNT(*) as total_plugins
FROM plugin_info;

-- 显示当前所有插件
SELECT 
    plugin_name,
    display_name,
    ide_type,
    current_version,
    is_active,
    is_primary,
    sort_order
FROM plugin_info 
ORDER BY sort_order, id;
