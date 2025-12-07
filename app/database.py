from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import time
from sqlalchemy import inspect, text
from dotenv import load_dotenv

# 从 .env 文件加载环境变量（如果存在）
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/windsurf_pool")

# SQLite 需要特殊配置
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库表，带重试机制"""
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # 尝试连接数据库并创建表
            Base.metadata.create_all(bind=engine)
            
            # 轻量迁移：确保 keys 表存在必要的列
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('keys')]
            
            # 迁移 account_limit 列
            if 'account_limit' not in columns:
                with engine.begin() as conn:
                    if engine.dialect.name == 'sqlite':
                        conn.execute(text("ALTER TABLE keys ADD COLUMN account_limit INTEGER NOT NULL DEFAULT 0"))
                    else:
                        conn.execute(text("ALTER TABLE keys ADD COLUMN IF NOT EXISTS account_limit INTEGER NOT NULL DEFAULT 0"))
                print("✅ 已添加 account_limit 列")
            
            # 迁移 key_type 列
            if 'key_type' not in columns:
                with engine.begin() as conn:
                    if engine.dialect.name == 'sqlite':
                        conn.execute(text("ALTER TABLE keys ADD COLUMN key_type VARCHAR NOT NULL DEFAULT 'limited'"))
                    else:
                        conn.execute(text("ALTER TABLE keys ADD COLUMN IF NOT EXISTS key_type VARCHAR NOT NULL DEFAULT 'limited'"))
                print("✅ 已添加 key_type 列")
            
            # 初始化版本配置
            from app.models import Config
            db = SessionLocal()
            try:
                # 检查是否已存在版本配置
                server_version = db.query(Config).filter(Config.key == "server_version").first()
                if not server_version:
                    db.add(Config(key="server_version", value="1.0.0", description="服务器版本号"))
                    print("✅ 已初始化 server_version 配置")
                
                min_client_version = db.query(Config).filter(Config.key == "min_client_version").first()
                if not min_client_version:
                    db.add(Config(key="min_client_version", value="1.0.0", description="最低客户端版本号"))
                    print("✅ 已初始化 min_client_version 配置")
                
                update_message = db.query(Config).filter(Config.key == "update_message").first()
                if not update_message:
                    db.add(Config(key="update_message", value="发现新版本，请立即更新客户端", description="版本更新提示信息"))
                    print("✅ 已初始化 update_message 配置")
                
                db.commit()
            except Exception as config_error:
                print(f"⚠️ 初始化版本配置失败: {config_error}")
                db.rollback()
            finally:
                db.close()
            
            # 如果成功，退出重试循环
            break
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ 数据库连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                print(f"⏳ {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
            else:
                print(f"❌ 数据库初始化失败，已重试 {max_retries} 次: {e}")
                raise
