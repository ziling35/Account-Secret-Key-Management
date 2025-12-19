"""
数据库迁移脚本：为账号表添加短期Token字段
- auth_token: One-Time Auth Token（短期）
- token_expires_at: Token过期时间

运行方式：
python migrate_auth_token.py
"""

import sqlite3
import os

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")

def migrate():
    """执行迁移"""
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 检查 accounts 表是否存在 auth_token 字段
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [col[1] for col in cursor.fetchall()]
        
        migrations_needed = []
        
        # 检查 accounts 表
        if 'auth_token' not in columns:
            migrations_needed.append(("accounts", "auth_token", "VARCHAR"))
        if 'token_expires_at' not in columns:
            migrations_needed.append(("accounts", "token_expires_at", "DATETIME"))
        
        # 检查 pro_accounts 表
        cursor.execute("PRAGMA table_info(pro_accounts)")
        pro_columns = [col[1] for col in cursor.fetchall()]
        
        if 'auth_token' not in pro_columns:
            migrations_needed.append(("pro_accounts", "auth_token", "VARCHAR"))
        if 'token_expires_at' not in pro_columns:
            migrations_needed.append(("pro_accounts", "token_expires_at", "DATETIME"))
        
        if not migrations_needed:
            print("✅ 数据库已是最新版本，无需迁移")
            return True
        
        # 执行迁移
        for table, column, col_type in migrations_needed:
            print(f"📦 正在添加字段: {table}.{column} ({col_type})")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        
        conn.commit()
        print(f"✅ 迁移完成！共添加 {len(migrations_needed)} 个字段")
        
        # 可选：清空旧的 api_key，让系统重新获取短期Token
        # cursor.execute("UPDATE accounts SET api_key = NULL, auth_token = NULL")
        # cursor.execute("UPDATE pro_accounts SET api_key = NULL, auth_token = NULL")
        # conn.commit()
        # print("✅ 已清空旧的 api_key，下次获取时将使用短期Token")
        
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移：添加短期Token字段")
    print("=" * 60)
    migrate()
