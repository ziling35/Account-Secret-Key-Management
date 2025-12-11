from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# 账号相关
class AccountBase(BaseModel):
    email: str
    name: str

class AccountCreate(BaseModel):
    email: str
    password: str
    api_key: str
    name: str

class AccountResponse(BaseModel):
    id: int
    email: str
    password: str
    api_key: str
    name: str
    status: str
    created_at: datetime
    assigned_at: Optional[datetime]
    assigned_to_key: Optional[str]
    
    class Config:
        from_attributes = True

# 密钥相关
class KeyCreate(BaseModel):
    key_type: str  # unlimited 或 limited
    duration_days: int
    account_limit: int
    notes: Optional[str] = None

class KeyResponse(BaseModel):
    id: int
    key_code: str
    key_type: str
    duration_days: int
    status: str
    is_disabled: bool = False
    created_at: datetime
    activated_at: Optional[datetime]
    expires_at: Optional[datetime]
    request_count: int
    last_request_at: Optional[datetime]
    last_request_ip: Optional[str]
    notes: Optional[str]
    remaining_time: Optional[str] = None
    account_limit: int
    remaining_accounts: Optional[int] = None
    daily_request_count: int = 0
    last_reset_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# 客户端请求
class AccountGetResponse(BaseModel):
    email: str
    api_key: str
    password: Optional[str] = None  # 有限额度时返回密码，无限额度不返回
    next_available_time: Optional[int] = None  # 下次可获取时间（秒数）

class KeyStatusResponse(BaseModel):
    status: str
    remaining_time: str
    request_count: int
    activated_at: Optional[datetime]
    expires_at: Optional[datetime]
    account_limit: int
    remaining_accounts: int

# 统计信息
class StatsResponse(BaseModel):
    total_accounts: int
    unused_accounts: int
    used_accounts: int
    expired_accounts: int
    total_keys: int
    inactive_keys: int
    active_keys: int
    expired_keys: int

# 版本控制
class VersionResponse(BaseModel):
    version: str
    min_client_version: str
    update_required: bool
    update_message: Optional[str] = None

# 公告相关
class AnnouncementResponse(BaseModel):
    """客户端公告响应"""
    content: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class AnnouncementCreate(BaseModel):
    """创建公告"""
    content: str
    is_active: bool = True

class AnnouncementUpdate(BaseModel):
    """更新公告"""
    content: Optional[str] = None
    is_active: Optional[bool] = None

class AnnouncementListItem(BaseModel):
    """公告列表项"""
    id: int
    content: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True

# 登录相关
class LoginRequest(BaseModel):
    """账号密码登录请求"""
    email: str
    password: str

class LoginResponse(BaseModel):
    """登录响应"""
    success: bool
    message: str
    data: Optional[dict] = None  # 包含 email, api_key, name 等信息
