from sqlalchemy import Column, Integer, String, DateTime, Boolean, Date, Enum as SQLEnum
from datetime import datetime
import enum
from app.database import Base

class AccountStatus(enum.Enum):
    unused = "unused"  # 未使用
    used = "used"      # 已使用
    expired = "expired"  # 已过期

class KeyStatus(enum.Enum):
    inactive = "inactive"  # 未激活
    active = "active"      # 已激活
    expired = "expired"    # 已过期

class KeyType(enum.Enum):
    unlimited = "unlimited"  # 无限额度（账号无限，5分钟限制）
    limited = "limited"      # 有限额度（账号有限，无频率限制）

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    api_key = Column(String, nullable=True)  # 允许为空，使用时自动获取
    name = Column(String, nullable=True)  # 允许为空，使用时自动获取
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.unused, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_at = Column(DateTime, nullable=True)
    assigned_to_key = Column(String, nullable=True)

class Key(Base):
    __tablename__ = "keys"
    
    id = Column(Integer, primary_key=True, index=True)
    key_code = Column(String, unique=True, index=True, nullable=False)
    key_type = Column(SQLEnum(KeyType), default=KeyType.limited, nullable=False)  # 密钥类型
    duration_days = Column(Integer, nullable=False)
    status = Column(SQLEnum(KeyStatus), default=KeyStatus.inactive, nullable=False)
    is_disabled = Column(Boolean, default=False, nullable=False)  # 是否被管理员禁用
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    activated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    request_count = Column(Integer, default=0, nullable=False)
    last_request_at = Column(DateTime, nullable=True)
    last_request_ip = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    account_limit = Column(Integer, default=0, nullable=False)
    # 无限额度专用：每日请求限制
    daily_request_count = Column(Integer, default=0, nullable=False)
    last_reset_date = Column(Date, nullable=True)  # 最后重置日期

class Config(Base):
    __tablename__ = "config"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Announcement(Base):
    __tablename__ = "announcements"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)  # 公告内容
    is_active = Column(Boolean, default=False, nullable=False, index=True)  # 是否启用
    priority = Column(Integer, default=0, nullable=False)  # 优先级（预留）
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String, nullable=True)  # 创建人
    updated_by = Column(String, nullable=True)  # 更新人
