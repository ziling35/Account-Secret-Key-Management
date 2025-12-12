"""
数据库迁移脚本：添加 plugin_info 表
运行方式: python migrate_plugin_info.py
"""

import sqlite3
import os
from datetime import datetime

# 数据库路径
DB_PATH = os.getenv("DATABASE_PATH", "data/app.db")

def migrate():
    """添加 plugin_info 表"""
    
    # 确保数据目录存在
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查表是否已存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plugin_info'")
    if cursor.fetchone():
        print("✅ plugin_info 表已存在，跳过创建")
    else:
        # 创建 plugin_info 表
        cursor.execute("""
            CREATE TABLE plugin_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name VARCHAR NOT NULL,
                current_version VARCHAR NOT NULL,
                min_version VARCHAR,
                download_url VARCHAR NOT NULL,
                changelog TEXT,
                update_title VARCHAR,
                update_description TEXT,
                is_force_update BOOLEAN DEFAULT 0 NOT NULL,
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                file_size VARCHAR,
                release_date DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX ix_plugin_info_plugin_name ON plugin_info (plugin_name)")
        cursor.execute("CREATE INDEX ix_plugin_info_is_active ON plugin_info (is_active)")
        
        print("✅ plugin_info 表创建成功")
        
        # 插入默认的插件信息
        now = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO plugin_info (
                plugin_name, current_version, min_version, download_url,
                changelog, update_title, update_description,
                is_force_update, is_active, file_size, release_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "windsurf-continue-pro",
            "1.0.0",
            "1.0.0",
            "https://your-server.com/plugins/windsurf-continue-pro-1.0.0.vsix",
            "### v1.0.0\n- 初始版本发布\n- 支持继续对话功能\n- 支持图片上传",
            "Windsurf Continue Pro 更新",
            "发现新版本，建议更新以获得更好的体验。",
            0,  # is_force_update
            1,  # is_active
            "31.87 KB",
            now,
            now,
            now
        ))
        
        print("✅ 已插入默认插件信息")
    
    conn.commit()
    conn.close()
    print("✅ 迁移完成")

if __name__ == "__main__":
    migrate()
