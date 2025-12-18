"""
数据库迁移脚本：添加Pro类型支持
- 账号表添加 is_pro 字段
- 卡密表的 key_type 已支持 'pro' 值（枚举自动扩展）

运行方式：python migrate_pro_type.py
"""

import sqlite3
import os

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'app.db')

def migrate():
    """执行迁移"""
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("请先运行应用程序创建数据库")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 检查 accounts 表是否存在 is_pro 字段
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_pro' not in columns:
            print("📝 添加 is_pro 字段到 accounts 表...")
            cursor.execute("""
                ALTER TABLE accounts 
                ADD COLUMN is_pro BOOLEAN DEFAULT 0 NOT NULL
            """)
            print("✅ is_pro 字段添加成功")
        else:
            print("ℹ️ is_pro 字段已存在，跳过")
        
        # 创建索引（如果不存在）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_accounts_is_pro 
            ON accounts (is_pro)
        """)
        print("✅ is_pro 索引创建/确认成功")
        
        conn.commit()
        print("\n✅ 迁移完成！")
        print("\n现在可以：")
        print("1. 在后台管理界面创建 'pro' 类型的卡密")
        print("2. 上传账号时勾选 'Pro账号' 选项")
        print("3. 在账号列表中切换账号的Pro状态")
        print("4. Pro卡密只能获取Pro账号，且客户端不需要安装插件")
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("Pro类型支持 - 数据库迁移脚本")
    print("=" * 50)
    print()
    migrate()
