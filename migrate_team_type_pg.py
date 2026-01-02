"""
PostgreSQL 数据库迁移脚本：为 keytype 枚举添加 'team' 值

运行方式：python migrate_team_type_pg.py

注意：此脚本用于 PostgreSQL 数据库
"""

import os
import psycopg2
from psycopg2 import sql

# 从环境变量获取数据库连接信息
DATABASE_URL = os.getenv("DATABASE_URL")

def migrate():
    """执行迁移：为 keytype 枚举添加 'team' 值"""
    if not DATABASE_URL:
        print("❌ 未设置 DATABASE_URL 环境变量")
        print("请设置 DATABASE_URL 环境变量，例如：")
        print("  export DATABASE_URL='postgresql://user:password@host:port/dbname'")
        return False
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True  # ALTER TYPE 不能在事务中运行
        cursor = conn.cursor()
        
        # 检查 'team' 值是否已存在于 keytype 枚举中
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'keytype')
                AND enumlabel = 'team'
            )
        """)
        exists = cursor.fetchone()[0]
        
        if exists:
            print("ℹ️ 'team' 值已存在于 keytype 枚举中，跳过")
        else:
            print("📝 为 keytype 枚举添加 'team' 值...")
            cursor.execute("ALTER TYPE keytype ADD VALUE 'team'")
            print("✅ 'team' 值添加成功")
        
        cursor.close()
        conn.close()
        
        print("\n✅ 迁移完成！")
        print("\n现在可以创建 'team' 类型的密钥了")
        return True
        
    except psycopg2.Error as e:
        print(f"❌ 数据库错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        return False

if __name__ == "__main__":
    migrate()
