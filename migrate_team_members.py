"""
数据库迁移脚本：创建团队成员管理相关表
用于固定Pro账号积分检测与自动切换功能
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.database import DATABASE_URL

def migrate():
    """执行迁移"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # 检查表是否已存在
        result = conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'team_configs'
        """))
        if result.fetchone():
            print("✅ 表 team_configs 已存在，跳过创建")
        else:
            # 创建 team_configs 表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS team_configs (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    key_code VARCHAR NOT NULL,
                    admin_email VARCHAR NOT NULL,
                    admin_password VARCHAR NOT NULL,
                    admin_api_key VARCHAR,
                    admin_token VARCHAR,
                    windsurf_team_id VARCHAR,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    credits_threshold INTEGER NOT NULL DEFAULT 20,
                    check_interval_minutes INTEGER NOT NULL DEFAULT 5,
                    current_member_id INTEGER,
                    last_check_at TIMESTAMP,
                    last_switch_at TIMESTAMP,
                    switch_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS ix_team_configs_key_code ON team_configs(key_code);
                CREATE INDEX IF NOT EXISTS ix_team_configs_is_active ON team_configs(is_active);
            """))
            print("✅ 已创建表 team_configs")
        
        # 检查 team_members 表
        result = conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'team_members'
        """))
        if result.fetchone():
            print("✅ 表 team_members 已存在，跳过创建")
        else:
            # 创建 team_members 表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS team_members (
                    id SERIAL PRIMARY KEY,
                    team_id INTEGER NOT NULL,
                    email VARCHAR NOT NULL,
                    password VARCHAR NOT NULL,
                    api_key VARCHAR,
                    name VARCHAR,
                    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    is_current BOOLEAN NOT NULL DEFAULT FALSE,
                    last_credits INTEGER NOT NULL DEFAULT 0,
                    last_check_at TIMESTAMP,
                    enabled_at TIMESTAMP,
                    disabled_at TIMESTAMP,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS ix_team_members_team_id ON team_members(team_id);
                CREATE INDEX IF NOT EXISTS ix_team_members_email ON team_members(email);
                CREATE INDEX IF NOT EXISTS ix_team_members_is_current ON team_members(is_current);
            """))
            print("✅ 已创建表 team_members")
        
        # 检查 member_switch_history 表
        result = conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'member_switch_history'
        """))
        if result.fetchone():
            print("✅ 表 member_switch_history 已存在，跳过创建")
        else:
            # 创建 member_switch_history 表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS member_switch_history (
                    id SERIAL PRIMARY KEY,
                    team_id INTEGER NOT NULL,
                    from_member_id INTEGER,
                    to_member_id INTEGER NOT NULL,
                    from_email VARCHAR,
                    to_email VARCHAR NOT NULL,
                    reason VARCHAR NOT NULL,
                    credits_before INTEGER,
                    switched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS ix_member_switch_history_team_id ON member_switch_history(team_id);
            """))
            print("✅ 已创建表 member_switch_history")
        
        conn.commit()
        print("\n🎉 团队成员管理表迁移完成！")


if __name__ == "__main__":
    print("=" * 60)
    print("团队成员管理数据库迁移")
    print("=" * 60)
    migrate()
