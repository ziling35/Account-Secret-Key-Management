-- =====================================================
-- 插件管理表 SQL 脚本
-- 用于 Windsurf 账号池管理系统
-- =====================================================

-- 创建 plugin_info 表
CREATE TABLE IF NOT EXISTS plugin_info (
    id SERIAL PRIMARY KEY,
    plugin_name VARCHAR(255) NOT NULL,
    current_version VARCHAR(50) NOT NULL,
    min_version VARCHAR(50),
    download_url VARCHAR(500) NOT NULL,
    changelog TEXT,
    update_title VARCHAR(255),
    update_description TEXT,
    is_force_update BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    file_size VARCHAR(50),
    release_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS ix_plugin_info_plugin_name ON plugin_info (plugin_name);
CREATE INDEX IF NOT EXISTS ix_plugin_info_is_active ON plugin_info (is_active);

-- 插入默认的插件信息
INSERT INTO plugin_info (
    plugin_name, 
    current_version, 
    min_version, 
    download_url,
    changelog, 
    update_title, 
    update_description,
    is_force_update, 
    is_active, 
    file_size, 
    release_date, 
    created_at, 
    updated_at
) VALUES (
    'windsurf-continue-pro',
    '1.0.0',
    '1.0.0',
    'https://your-server.com/plugins/windsurf-continue-pro-1.0.0.vsix',
    '### v1.0.0
- 初始版本发布
- 支持继续对话功能
- 支持图片上传
- 会话窗口关闭后可重新打开',
    'Windsurf Continue Pro 更新',
    '发现新版本，建议更新以获得更好的体验。',
    FALSE,
    TRUE,
    '33.33 KB',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

-- 查看插入结果
SELECT * FROM plugin_info;
