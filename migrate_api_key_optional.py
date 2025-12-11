"""
数据库迁移脚本：将 api_key 和 name 字段改为可选
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./windsurf_pool.db")

def migrate():
    """执行迁移"""
    engine = create_engine(DATABASE_URL)
    
    print("开始数据库迁移...")
    print(f"数据库: {DATABASE_URL}")
    
    with engine.connect() as conn:
        try:
            # 检查数据库类型
            if "postgresql" in DATABASE_URL:
                # PostgreSQL
                print("\n检测到 PostgreSQL 数据库")
                
                # 修改 api_key 字段为可空
                print("1. 修改 api_key 字段为可空...")
                conn.execute(text("""
                    ALTER TABLE accounts 
                    ALTER COLUMN api_key DROP NOT NULL
                """))
                
                # 修改 name 字段为可空
                print("2. 修改 name 字段为可空...")
                conn.execute(text("""
                    ALTER TABLE accounts 
                    ALTER COLUMN name DROP NOT NULL
                """))
                
                conn.commit()
                print("✅ PostgreSQL 迁移完成！")
                
            elif "sqlite" in DATABASE_URL:
                # SQLite 不支持直接修改列约束，需要重建表
                print("\n检测到 SQLite 数据库")
                print("SQLite 需要重建表来修改列约束...")
                
                # 1. 创建新表
                print("1. 创建新表结构...")
                conn.execute(text("""
                    CREATE TABLE accounts_new (
                        id INTEGER PRIMARY KEY,
                        email VARCHAR NOT NULL UNIQUE,
                        password VARCHAR NOT NULL,
                        api_key VARCHAR,
                        name VARCHAR,
                        status VARCHAR NOT NULL DEFAULT 'unused',
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        assigned_at TIMESTAMP,
                        assigned_to_key VARCHAR
                    )
                """))
                
                # 2. 复制数据
                print("2. 复制数据到新表...")
                conn.execute(text("""
                    INSERT INTO accounts_new 
                    SELECT id, email, password, api_key, name, status, 
                           created_at, assigned_at, assigned_to_key
                    FROM accounts
                """))
                
                # 3. 删除旧表
                print("3. 删除旧表...")
                conn.execute(text("DROP TABLE accounts"))
                
                # 4. 重命名新表
                print("4. 重命名新表...")
                conn.execute(text("ALTER TABLE accounts_new RENAME TO accounts"))
                
                # 5. 重建索引
                print("5. 重建索引...")
                conn.execute(text("""
                    CREATE UNIQUE INDEX ix_accounts_email ON accounts (email)
                """))
                conn.execute(text("""
                    CREATE INDEX ix_accounts_id ON accounts (id)
                """))
                
                conn.commit()
                print("✅ SQLite 迁移完成！")
            
            else:
                print("❌ 不支持的数据库类型")
                return False
            
            print("\n" + "="*60)
            print("✅ 数据库迁移成功完成！")
            print("="*60)
            print("\n现在可以上传不包含 API Key 的账号文件了。")
            print("系统会在分配账号时自动通过登录获取 API Key。")
            
            return True
            
        except Exception as e:
            print(f"\n❌ 迁移失败: {str(e)}")
            conn.rollback()
            return False

if __name__ == "__main__":
    migrate()
