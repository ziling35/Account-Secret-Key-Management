"""
数据库迁移脚本：添加设备绑定功能
- 在 keys 表添加 max_devices 字段
- 创建 device_bindings 表
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库连接
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ 错误: 未找到 DATABASE_URL 环境变量")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def migrate():
    """执行迁移"""
    with engine.connect() as conn:
        print("🔄 开始数据库迁移...")
        
        # 1. 检查 keys 表是否已有 max_devices 字段
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='keys' AND column_name='max_devices'
            """))
            if result.fetchone():
                print("✅ keys.max_devices 字段已存在，跳过")
            else:
                # 添加 max_devices 字段
                conn.execute(text("""
                    ALTER TABLE keys 
                    ADD COLUMN max_devices INTEGER NOT NULL DEFAULT 1
                """))
                conn.commit()
                print("✅ 已添加 keys.max_devices 字段")
        except Exception as e:
            print(f"⚠️  检查/添加 max_devices 字段时出错: {e}")
        
        # 2. 检查 device_bindings 表是否存在
        try:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='device_bindings'
            """))
            if result.fetchone():
                print("✅ device_bindings 表已存在，跳过")
            else:
                # 创建 device_bindings 表
                conn.execute(text("""
                    CREATE TABLE device_bindings (
                        id SERIAL PRIMARY KEY,
                        key_code VARCHAR NOT NULL,
                        device_id VARCHAR NOT NULL,
                        device_name VARCHAR,
                        first_bound_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_active_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        request_count INTEGER NOT NULL DEFAULT 0,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE
                    )
                """))
                
                # 创建索引
                conn.execute(text("""
                    CREATE INDEX ix_device_bindings_key_code ON device_bindings(key_code)
                """))
                conn.execute(text("""
                    CREATE INDEX ix_device_bindings_device_id ON device_bindings(device_id)
                """))
                
                conn.commit()
                print("✅ 已创建 device_bindings 表和索引")
        except Exception as e:
            print(f"⚠️  检查/创建 device_bindings 表时出错: {e}")
        
        print("✅ 数据库迁移完成！")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        sys.exit(1)
