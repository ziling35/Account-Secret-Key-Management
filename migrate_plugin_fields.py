"""
数据库迁移脚本：为 plugin_info 表添加客户端展示字段
运行此脚本以更新现有数据库结构
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取数据库连接
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("错误: 未找到 DATABASE_URL 环境变量")
    exit(1)

engine = create_engine(DATABASE_URL)

# 迁移SQL语句
migration_sql = """
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

-- 修改 changelog 和 update_description 为 TEXT 类型（支持更长内容）
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

-- 创建 ide_type 索引
CREATE INDEX IF NOT EXISTS ix_plugin_info_ide_type ON plugin_info (ide_type);

-- 查看迁移结果
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'plugin_info'
ORDER BY ordinal_position;
"""

try:
    print("开始数据库迁移...")
    with engine.connect() as conn:
        # 执行迁移
        conn.execute(text(migration_sql))
        conn.commit()
        print("✅ 数据库迁移成功完成！")
        
        # 显示当前插件列表
        result = conn.execute(text("SELECT plugin_name, display_name, ide_type, sort_order FROM plugin_info ORDER BY sort_order"))
        plugins = result.fetchall()
        
        if plugins:
            print(f"\n当前数据库中的插件 ({len(plugins)} 个):")
            for p in plugins:
                print(f"  - {p[0]} ({p[1] or 'N/A'}) - IDE: {p[2]}, 排序: {p[3]}")
        else:
            print("\n⚠️ 数据库中暂无插件数据")
            print("提示: 运行 plugin_info_update.sql 来插入示例数据")
            
except Exception as e:
    print(f"❌ 迁移失败: {str(e)}")
    exit(1)
