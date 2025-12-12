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

# 账号历史相关
class AccountHistoryItem(BaseModel):
    """账号历史项"""
    email: str
    password: str
    api_key: Optional[str] = None
    name: Optional[str] = None
    assigned_at: Optional[datetime] = None

class AccountHistoryResponse(BaseModel):
    """账号历史响应"""
    success: bool
    message: str
    accounts: list[AccountHistoryItem] = []
    total: int = 0

# 版本说明相关
class VersionNoteCreate(BaseModel):
    """创建版本说明"""
    version: str
    title: str
    content: str
    release_date: Optional[datetime] = None
    is_published: bool = True

class VersionNoteUpdate(BaseModel):
    """更新版本说明"""
    version: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    release_date: Optional[datetime] = None
    is_published: Optional[bool] = None

class VersionNoteItem(BaseModel):
    """版本说明项"""
    id: int
    version: str
    title: str
    content: str
    release_date: datetime
    is_published: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class VersionNotesResponse(BaseModel):
    """版本说明列表响应"""
    success: bool
    message: str
    notes: list[VersionNoteItem] = []
    total: int = 0


# 插件管理相关
class PluginInfoResponse(BaseModel):
    """插件信息响应（客户端用）"""
    plugin_name: str
    current_version: str
    min_version: Optional[str] = None
    download_url: str
    changelog: Optional[str] = None
    update_title: Optional[str] = None
    update_description: Optional[str] = None
    is_force_update: bool = False
    file_size: Optional[str] = None
    release_date: Optional[datetime] = None

class PluginListItem(BaseModel):
    """插件列表项（客户端用）"""
    name: str  # 插件名称
    display_name: str  # 显示名称
    description: Optional[str] = None  # 插件描述
    ide_type: str = "windsurf"  # IDE 类型: windsurf, kiro
    latest_version: str  # 最新版本
    download_url: Optional[str] = None  # 下载地址
    icon: str = "puzzle"  # 图标名称 (lucide icon)
    icon_gradient: list[str] = ["#667eea", "#764ba2"]  # 图标渐变色
    features: list[dict] = []  # 功能列表 [{"title": "xxx", "description": "xxx"}]
    usage_steps: list[dict] = []  # 使用步骤 [{"step": 1, "title": "xxx", "description": "xxx"}]
    tips: list[dict] = []  # 提示信息 [{"type": "success|warning", "title": "xxx", "content": "xxx"}]
    is_disabled: bool = False  # 是否禁用
    is_primary: bool = False  # 是否主插件

class PluginListResponse(BaseModel):
    """插件列表响应（客户端用）"""
    success: bool = True
    plugins: list[PluginListItem] = []

class PluginVersionCheckResponse(BaseModel):
    """插件版本检查响应"""
    has_update: bool
    is_force_update: bool = False
    current_version: str
    latest_version: str
    download_url: Optional[str] = None
    update_title: Optional[str] = None
    update_description: Optional[str] = None
    changelog: Optional[str] = None
    file_size: Optional[str] = None

class PluginInfoCreate(BaseModel):
    """创建插件信息（管理端用）"""
    plugin_name: str
    current_version: str
    min_version: Optional[str] = None
    download_url: str
    changelog: Optional[str] = None
    update_title: Optional[str] = None
    update_description: Optional[str] = None
    is_force_update: bool = False
    is_active: bool = True
    file_size: Optional[str] = None

class PluginInfoUpdate(BaseModel):
    """更新插件信息（管理端用）"""
    current_version: Optional[str] = None
    min_version: Optional[str] = None
    download_url: Optional[str] = None
    changelog: Optional[str] = None
    update_title: Optional[str] = None
    update_description: Optional[str] = None
    is_force_update: Optional[bool] = None
    is_active: Optional[bool] = None
    file_size: Optional[str] = None

class PluginInfoListItem(BaseModel):
    """插件信息列表项（管理端用）"""
    id: int
    plugin_name: str
    current_version: str
    min_version: Optional[str] = None
    download_url: str
    changelog: Optional[str] = None
    update_title: Optional[str] = None
    update_description: Optional[str] = None
    is_force_update: bool
    is_active: bool
    file_size: Optional[str] = None
    release_date: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
