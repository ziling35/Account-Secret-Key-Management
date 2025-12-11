import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List, Dict

# 中国时区 UTC+8
CHINA_TZ = timezone(timedelta(hours=8))

def generate_key_code(length: int = 10) -> str:
    """生成随机密钥代码"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def parse_account_file(content: str) -> List[Dict[str, str]]:
    """
    解析账号批量文件
    支持中英文格式：
    账号 1: 或 Account 1:
      邮箱: 或 Email:
      姓名: 或 Name:
      密码: 或 Password:
      API密钥: 或 API Key: (可选)
    
    注意：API Key 为可选字段，如果没有提供，将在使用时自动通过登录获取
    """
    accounts = []
    
    # 按账号分割（支持中英文）
    account_blocks = re.split(r'(?:账号|Account)\s*\d+\s*[:：]', content)
    
    for block in account_blocks:
        if not block.strip():
            continue
            
        # 提取字段（支持中英文，支持中英文冒号）
        email_match = re.search(r'(?:邮箱|Email)\s*[:：]\s*(.+)', block, re.IGNORECASE)
        name_match = re.search(r'(?:姓名|Name)\s*[:：]\s*(.+)', block, re.IGNORECASE)
        password_match = re.search(r'(?:密码|Password)\s*[:：]\s*(.+)', block, re.IGNORECASE)
        api_key_match = re.search(r'(?:API密钥|API\s*Key)\s*[:：]\s*(.+)', block, re.IGNORECASE)
        
        # 必须有邮箱、姓名和密码，API Key 可选
        if all([email_match, name_match, password_match]):
            account_data = {
                'email': email_match.group(1).strip(),
                'name': name_match.group(1).strip(),
                'password': password_match.group(1).strip(),
                'api_key': api_key_match.group(1).strip() if api_key_match else ''
            }
            accounts.append(account_data)
    
    return accounts

def calculate_remaining_time(expires_at: datetime) -> str:
    """
    计算剩余时间
    注意：数据库中存储的是 UTC 时间（naive datetime），需要转换为本地时区显示
    """
    if not expires_at:
        return "未激活"
    
    # 获取当前 UTC 时间
    now_utc = datetime.utcnow()
    
    # expires_at 从数据库读取时是 naive datetime（UTC），直接比较
    if now_utc >= expires_at:
        return "已过期"
    
    # 计算时间差
    delta = expires_at - now_utc
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    
    if days > 0:
        return f"{days}天{hours}小时"
    elif hours > 0:
        return f"{hours}小时{minutes}分钟"
    else:
        return f"{minutes}分钟"

def format_datetime(dt: datetime) -> str:
    """格式化时间"""
    if not dt:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")
