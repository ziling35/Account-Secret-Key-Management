"""
数据库迁移脚本 - 添加账号获取历史表
"""
import sqlite3
import os

def run_migration():
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'app.db')
    sql_path = os.path.join(os.path.dirname(__file__), 'migrations', 'add_account_assignment_history.sql')
    
    print(f"数据库路径: {db_path}")
    print(f"SQL文件路径: {sql_path}")
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        return False
    
    if not os.path.exists(sql_path):
        print(f"错误: SQL文件不存在: {sql_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        conn.executescript(sql_content)
        conn.commit()
        conn.close()
        
        print("✅ 迁移完成！已创建 account_assignment_history 表")
        return True
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        return False

if __name__ == "__main__":
    run_migration()
