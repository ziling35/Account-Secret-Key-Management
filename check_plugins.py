from app.database import engine, SessionLocal
from app.models import PluginInfo
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"数据库表: {tables}")

if 'plugin_info' in tables:
    print("\n✓ plugin_info 表存在")
    
    db = SessionLocal()
    try:
        plugins = db.query(PluginInfo).all()
        print(f"\n插件数量: {len(plugins)}")
        
        if plugins:
            print("\n插件列表:")
            for p in plugins:
                print(f"  - ID: {p.id}")
                print(f"    名称: {p.plugin_name}")
                print(f"    版本: {p.current_version}")
                print(f"    状态: {'启用' if p.is_active else '禁用'}")
                print(f"    下载地址: {p.download_url}")
                print()
        else:
            print("\n⚠ 数据库中没有插件数据！")
            print("需要添加插件数据才能在页面上看到。")
    finally:
        db.close()
else:
    print("\n✗ plugin_info 表不存在！")
    print("需要运行数据库迁移或执行 plugin_info.sql 脚本。")
