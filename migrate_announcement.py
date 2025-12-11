"""
数据库迁移脚本 - 添加公告表
运行此脚本以在现有数据库中创建 announcements 表
"""

from app.database import engine, Base
from app.models import Announcement
from sqlalchemy import inspect

def migrate_announcement_table():
    """创建公告表"""
    inspector = inspect(engine)
    
    # 检查表是否已存在
    if 'announcements' in inspector.get_table_names():
        print("✅ announcements 表已存在，跳过创建")
        return
    
    print("📝 正在创建 announcements 表...")
    
    # 只创建 Announcement 表
    Announcement.__table__.create(engine)
    
    print("✅ announcements 表创建成功！")
    
    # 插入示例公告
    from sqlalchemy.orm import Session
    db = Session(engine)
    
    try:
        example_announcement = Announcement(
            content="欢迎使用 PaperCrane-Windsurf！\n\n最新更新：\n- 新增公告功能\n- 优化账号切换速度\n- 修复已知问题\n\n如有问题请联系管理员。",
            is_active=True,
            created_by="system"
        )
        db.add(example_announcement)
        db.commit()
        print("✅ 示例公告已添加")
    except Exception as e:
        print(f"⚠️  添加示例公告失败: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("公告功能数据库迁移")
    print("=" * 60)
    migrate_announcement_table()
    print("=" * 60)
    print("迁移完成！")
