-- =====================================================
-- 插件信息表扩展 SQL 脚本
-- 添加客户端展示所需的字段
-- =====================================================

-- 添加新字段到 plugin_info 表
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

-- 创建 ide_type 索引
CREATE INDEX IF NOT EXISTS ix_plugin_info_ide_type ON plugin_info (ide_type);

-- 更新现有的 windsurf-continue-pro 记录
UPDATE plugin_info SET
    display_name = 'Windsurf Continue Pro',
    description = '专属定制版 - 与卡密系统完全打通',
    ide_type = 'windsurf',
    icon = 'shield-check',
    icon_gradient = '["#667eea", "#764ba2"]',
    features = '[
        {"title": "与卡密完全打通", "description": "自动使用当前激活的卡密"},
        {"title": "安全验证", "description": "定期检查卡密有效性，到期自动停止"},
        {"title": "AI 持续对话", "description": "在同一对话中继续，不消耗新 credits"},
        {"title": "专业界面", "description": "Windows 原生 GUI 对话框"}
    ]',
    usage_steps = '[
        {"step": 1, "title": "一键安装", "description": "点击「一键安装」按钮，自动完成安装、激活、配置 MCP、安装规则并重启 Windsurf"},
        {"step": 2, "title": "开始使用", "description": "在 Windsurf 中正常使用 Cascade，AI 结束时会自动弹出对话框"}
    ]',
    tips = '[
        {"type": "success", "title": "激活码自动同步", "content": "客户端和插件共享激活码，一次激活全部搞定！插件启动时会自动读取客户端的激活状态，无需重复输入卡密。"},
        {"type": "warning", "title": "工作原理", "content": "插件通过 MCP 机制拦截 AI 的结束行为，让 AI 在同一对话中继续，不会消耗额外的 credits。这才是真正的「永不停止」！"}
    ]',
    mcp_config_path = '~/.codeium/windsurf/mcp_config.json',
    extensions_path = '~/.windsurf/extensions',
    mcp_extra_config = '{}',
    is_primary = TRUE,
    sort_order = 1
WHERE plugin_name = 'windsurf-continue-pro';

-- 先添加唯一约束（如果不存在）
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'plugin_info_plugin_name_key'
    ) THEN
        ALTER TABLE plugin_info ADD CONSTRAINT plugin_info_plugin_name_key UNIQUE (plugin_name);
    END IF;
END $$;

-- 插入 Kiro 插件记录（如果不存在则插入，存在则更新）
INSERT INTO plugin_info (
    plugin_name,
    display_name,
    description,
    ide_type,
    current_version,
    min_version,
    download_url,
    changelog,
    update_title,
    update_description,
    is_force_update,
    is_active,
    file_size,
    icon,
    icon_gradient,
    features,
    usage_steps,
    tips,
    mcp_config_path,
    extensions_path,
    mcp_extra_config,
    is_primary,
    sort_order,
    release_date,
    created_at,
    updated_at
) VALUES (
    'kiro-continue-pro',
    'Kiro Continue Pro',
    'Kiro IDE 专属版本 - 支持自动批准',
    'kiro',
    '1.0.0',
    '1.0.0',
    'https://your-server.com/plugins/kiro-continue-pro-1.0.0.vsix',
    '### v1.0.0
- 初始版本发布
- 支持 Kiro IDE
- 自动批准 MCP 调用
- 支持继续对话功能',
    'Kiro Continue Pro 更新',
    '发现新版本，建议更新以获得更好的体验。',
    FALSE,
    TRUE,
    '33.33 KB',
    'sparkles',
    '["#8b5cf6", "#6366f1"]',
    '[
        {"title": "与卡密完全打通", "description": "自动使用当前激活的卡密"},
        {"title": "自动批准 MCP 调用", "description": "无需手动确认，自动批准工具调用"},
        {"title": "AI 持续对话", "description": "在同一对话中继续，不消耗新 credits"}
    ]',
    '[
        {"step": 1, "title": "安装到 Kiro", "description": "点击「安装到 Kiro」按钮安装插件"},
        {"step": 2, "title": "配置 MCP", "description": "点击「配置 Kiro MCP」按钮完成配置"},
        {"step": 3, "title": "重启 Kiro", "description": "重启 Kiro IDE 使配置生效"}
    ]',
    '[]',
    '~/.kiro/settings/mcp.json',
    '~/.kiro/extensions',
    '{"autoApprove": ["ask_continue"]}',
    FALSE,
    2,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (plugin_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    ide_type = EXCLUDED.ide_type,
    icon = EXCLUDED.icon,
    icon_gradient = EXCLUDED.icon_gradient,
    features = EXCLUDED.features,
    usage_steps = EXCLUDED.usage_steps,
    tips = EXCLUDED.tips,
    mcp_config_path = EXCLUDED.mcp_config_path,
    extensions_path = EXCLUDED.extensions_path,
    mcp_extra_config = EXCLUDED.mcp_extra_config,
    is_primary = EXCLUDED.is_primary,
    sort_order = EXCLUDED.sort_order,
    updated_at = CURRENT_TIMESTAMP;

-- 查看更新结果
SELECT 
    plugin_name, 
    display_name, 
    ide_type, 
    current_version, 
    icon, 
    is_primary, 
    sort_order,
    mcp_config_path
FROM plugin_info 
ORDER BY sort_order;
