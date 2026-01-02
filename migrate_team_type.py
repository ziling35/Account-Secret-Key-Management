"""
数据库迁移脚本 - 添加Team卡密类型支持

执行步骤：
1. 在 keys 表添加 team_card_key 字段
2. 创建 team_login_cache 表
3. 更新 key_type 枚举（如果需要）
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect

# 获取数据库URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/accounts.db")

def run_migration():
    print("=" * 60)
    print("Team卡密类型迁移脚本")
    print("=" * 60)
    
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        # 1. 检查并添加 team_card_key 字段到 keys 表
        print("\n[1/2] 检查 keys 表的 team_card_key 字段...")
        columns = [col['name'] for col in inspector.get_columns('keys')]
        
        if 'team_card_key' not in columns:
            print("  - 添加 team_card_key 字段...")
            if 'sqlite' in DATABASE_URL:
                conn.execute(text("ALTER TABLE keys ADD COLUMN team_card_key VARCHAR"))
            else:  # PostgreSQL
                conn.execute(text("ALTER TABLE keys ADD COLUMN team_card_key VARCHAR"))
            conn.commit()
            print("  ✅ team_card_key 字段添加成功")
        else:
            print("  ✅ team_card_key 字段已存在")
        
        # 2. 创建 team_login_cache 表
        print("\n[2/2] 检查 team_login_cache 表...")
        tables = inspector.get_table_names()
        
        if 'team_login_cache' not in tables:
            print("  - 创建 team_login_cache 表...")
            if 'sqlite' in DATABASE_URL:
                conn.execute(text("""
                    CREATE TABLE team_login_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_code VARCHAR NOT NULL,
                        team_card_key VARCHAR NOT NULL,
                        callback_url VARCHAR NOT NULL,
                        email VARCHAR NOT NULL,
                        nickname VARCHAR,
                        cached_at DATETIME NOT NULL,
                        expires_at DATETIME NOT NULL
                    )
                """))
                conn.execute(text("CREATE UNIQUE INDEX ix_team_login_cache_key_code ON team_login_cache (key_code)"))
            else:  # PostgreSQL
                conn.execute(text("""
                    CREATE TABLE team_login_cache (
                        id SERIAL PRIMARY KEY,
                        key_code VARCHAR NOT NULL,
                        team_card_key VARCHAR NOT NULL,
                        callback_url VARCHAR NOT NULL,
                        email VARCHAR NOT NULL,
                        nickname VARCHAR,
                        cached_at TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP NOT NULL
                    )
                """))
                conn.execute(text("CREATE UNIQUE INDEX ix_team_login_cache_key_code ON team_login_cache (key_code)"))
            conn.commit()
            print("  ✅ team_login_cache 表创建成功")
        else:
            print("  ✅ team_login_cache 表已存在")
    
    print("\n" + "=" * 60)
    print("✅ 迁移完成！")
    print("=" * 60)
    print("\nTeam卡密类型现已可用。")
    print("在管理后台创建卡密时：")
    print("  1. 选择类型为 'team'")
    print("  2. 填写第三方卡密到 team_card_key 字段")
    print("=" * 60)

if __name__ == "__main__":
    run_migration()
