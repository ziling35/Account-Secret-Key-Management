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

class VersionNote(Base):
    """版本说明"""
    __tablename__ = "version_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, nullable=False, index=True)  # 版本号，如 1.0.0
    title = Column(String, nullable=False)  # 版本标题
    content = Column(String, nullable=False)  # 版本说明内容（支持 Markdown）
    release_date = Column(DateTime, default=datetime.utcnow, nullable=False)  # 发布日期
    is_published = Column(Boolean, default=True, nullable=False, index=True)  # 是否发布
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PluginInfo(Base):
    """插件信息管理"""
    __tablename__ = "plugin_info"
    
    id = Column(Integer, primary_key=True, index=True)
    plugin_name = Column(String, nullable=False, index=True)  # 插件名称，如 windsurf-continue-pro
    current_version = Column(String, nullable=False)  # 当前版本号，如 1.0.0
    min_version = Column(String, nullable=True)  # 最低支持版本（低于此版本强制更新）
    download_url = Column(String, nullable=False)  # 插件下载地址
    changelog = Column(String, nullable=True)  # 更新日志（支持 Markdown）
    update_title = Column(String, nullable=True)  # 更新标题
    update_description = Column(String, nullable=True)  # 更新描述（弹窗显示）
    is_force_update = Column(Boolean, default=False, nullable=False)  # 是否强制更新
    is_active = Column(Boolean, default=True, nullable=False, index=True)  # 是否启用
    file_size = Column(String, nullable=True)  # 文件大小，如 "31.87 KB"
    release_date = Column(DateTime, default=datetime.utcnow, nullable=False)  # 发布日期
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
