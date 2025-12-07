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
