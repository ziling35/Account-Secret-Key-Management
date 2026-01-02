"""
数据库迁移脚本：为 keys 表添加 last_pro_switch_at 字段
解决问题：Pro切号接口与其他接口共享 last_request_at 导致频率限制误判
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine, SessionLocal

def migrate():
    """添加 last_pro_switch_at 字段到 keys 表"""
    db = SessionLocal()
    
    try:
        # 检查字段是否已存在
        check_sql = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'keys' AND column_name = 'last_pro_switch_at'
        """
        
        result = db.execute(text(check_sql)).fetchone()
        
        if result:
            print("✅ 字段 last_pro_switch_at 已存在，无需迁移")
            return True
        
        # 添加新字段
        alter_sql = """
        ALTER TABLE keys ADD COLUMN last_pro_switch_at TIMESTAMP NULL
        """
        
        db.execute(text(alter_sql))
        db.commit()
        
        print("✅ 成功添加 last_pro_switch_at 字段到 keys 表")
        print("   - 该字段用于Pro切号接口的独立频率限制")
        print("   - 解决了与其他接口共享 last_request_at 导致的误判问题")
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 50)
    print("Pro切号字段迁移脚本")
    print("=" * 50)
    migrate()
