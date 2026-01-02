from sqlalchemy import Column, Integer, String, DateTime, Boolean, Date, Enum as SQLEnum, Text, JSON
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
    pro = "pro"              # Pro类型（只能获取pro账号，无插件限制）
    team = "team"            # Team类型（一键切号，通过第三方API获取登录URL）

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    api_key = Column(String, nullable=True)  # 允许为空，使用时自动获取
    name = Column(String, nullable=True)  # 允许为空，使用时自动获取
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.unused, nullable=False)
    is_pro = Column(Boolean, default=False, nullable=False, index=True)  # 是否为Pro账号
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_at = Column(DateTime, nullable=True)
    assigned_to_key = Column(String, nullable=True)

class ProAccount(Base):
    """Pro账号表（允许重复邮箱）"""
    __tablename__ = "pro_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)  # 不设置 unique，允许重复
    password = Column(String, nullable=False)
    api_key = Column(String, nullable=True)
    name = Column(String, nullable=True)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.unused, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_at = Column(DateTime, nullable=True)
    assigned_to_key = Column(String, nullable=True)

class Key(Base):
    __tablename__ = "keys"
    
    id = Column(Integer, primary_key=True, index=True)
    key_code = Column(String, unique=True, index=True, nullable=False)
    key_type = Column(SQLEnum(KeyType), default=KeyType.limited, nullable=False)  # 密钥类型
    duration_days = Column(Integer, nullable=False, default=0)
    duration_hours = Column(Integer, nullable=False, default=0)  # 小时卡支持
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
    # 设备绑定限制
    max_devices = Column(Integer, default=1, nullable=False)  # 最大设备绑定数，默认1台
    # Team卡密专用字段
    team_card_key = Column(String, nullable=True)  # 第三方卡密（team类型必填）
    # Pro切号专用字段（独立冷却时间戳）
    last_pro_switch_at = Column(DateTime, nullable=True)  # 上次Pro切号时间
    # 关联团队配置（用于积分检测和自动切换）
    team_id = Column(Integer, nullable=True)  # 关联的团队ID

class DeviceBinding(Base):
    """设备绑定记录表"""
    __tablename__ = "device_bindings"
    
    id = Column(Integer, primary_key=True, index=True)
    key_code = Column(String, nullable=False, index=True)  # 密钥
    device_id = Column(String, nullable=False, index=True)  # 设备唯一标识（机器码）
    device_name = Column(String, nullable=True)  # 设备名称（可选）
    first_bound_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 首次绑定时间
    last_active_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 最后活跃时间
    request_count = Column(Integer, default=0, nullable=False)  # 该设备的请求次数
    is_active = Column(Boolean, default=True, nullable=False)  # 是否激活（用于解绑）


class TeamLoginCache(Base):
    """Team卡密登录缓存表"""
    __tablename__ = "team_login_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    key_code = Column(String, nullable=False, index=True, unique=True)  # 密钥（一个密钥一条缓存）
    team_card_key = Column(String, nullable=False)  # 第三方卡密
    callback_url = Column(String, nullable=False)  # 登录回调URL
    email = Column(String, nullable=False)  # 账号邮箱
    nickname = Column(String, nullable=True)  # 账号昵称
    cached_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 缓存时间
    expires_at = Column(DateTime, nullable=False)  # 过期时间（10分钟后）

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


class AccountAssignmentHistory(Base):
    """账号获取历史（用于记录Pro卡密等可重复获取账号的历史）"""
    __tablename__ = "account_assignment_history"
    
    id = Column(Integer, primary_key=True, index=True)
    key_code = Column(String, nullable=False, index=True)  # 密钥
    account_id = Column(Integer, nullable=False, index=True)  # 账号ID
    email = Column(String, nullable=False)  # 账号邮箱
    password = Column(String, nullable=True)  # 账号密码
    api_key = Column(String, nullable=True)  # API Key
    name = Column(String, nullable=True)  # 账号名称
    is_pro = Column(Boolean, default=False, nullable=False)  # 是否为Pro账号
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 获取时间


class PluginInfo(Base):
    """插件信息管理"""
    __tablename__ = "plugin_info"
    
    id = Column(Integer, primary_key=True, index=True)
    plugin_name = Column(String, nullable=False, index=True, unique=True)  # 插件名称，如 windsurf-continue-pro
    
    # 基础版本管理字段
    current_version = Column(String, nullable=False)  # 当前版本号，如 1.0.0
    min_version = Column(String, nullable=True)  # 最低支持版本（低于此版本强制更新）
    download_url = Column(String, nullable=False)  # 插件下载地址
    changelog = Column(Text, nullable=True)  # 更新日志（支持 Markdown）
    update_title = Column(String, nullable=True)  # 更新标题
    update_description = Column(Text, nullable=True)  # 更新描述（弹窗显示）
    is_force_update = Column(Boolean, default=False, nullable=False)  # 是否强制更新
    is_active = Column(Boolean, default=True, nullable=False, index=True)  # 是否启用
    file_size = Column(String, nullable=True)  # 文件大小，如 "31.87 KB"
    release_date = Column(DateTime, default=datetime.utcnow, nullable=False)  # 发布日期
    
    # 客户端展示字段
    display_name = Column(String(100), nullable=True)  # 显示名称，如 "Windsurf Continue Pro"
    description = Column(Text, nullable=True)  # 插件描述
    ide_type = Column(String(50), default='windsurf', nullable=False, index=True)  # IDE类型: windsurf, kiro
    icon = Column(String(50), default='shield-check', nullable=True)  # 图标名称（Lucide图标）
    icon_gradient = Column(JSON, nullable=True)  # 图标渐变色，如 ["#667eea", "#764ba2"]
    features = Column(JSON, nullable=True)  # 功能特性列表，如 [{"title": "...", "description": "..."}]
    usage_steps = Column(JSON, nullable=True)  # 使用步骤，如 [{"step": 1, "title": "...", "description": "..."}]
    tips = Column(JSON, nullable=True)  # 提示信息，如 [{"type": "success", "title": "...", "content": "..."}]
    mcp_config_path = Column(String(255), nullable=True)  # MCP配置文件路径
    extensions_path = Column(String(255), nullable=True)  # 扩展安装路径
    mcp_extra_config = Column(JSON, nullable=True)  # MCP额外配置，如 {"autoApprove": ["ask_continue"]}
    is_primary = Column(Boolean, default=False, nullable=False)  # 是否主要插件
    sort_order = Column(Integer, default=0, nullable=False)  # 排序顺序
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ==================== 团队成员管理（固定Pro账号积分检测与自动切换） ====================

class TeamConfig(Base):
    """团队配置（多个Pro卡密可关联到同一个团队）"""
    __tablename__ = "team_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # 团队名称
    # 注意：key_code字段已移除，改为在Key表中通过team_id关联
    admin_email = Column(String, nullable=False)  # 管理员邮箱
    admin_password = Column(String, nullable=False)  # 管理员密码
    admin_api_key = Column(String, nullable=True)  # 管理员API Key
    admin_token = Column(String, nullable=True)  # 管理员Token（用于调用Windsurf API）
    windsurf_team_id = Column(String, nullable=True)  # Windsurf团队ID
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    credits_threshold = Column(Integer, default=20, nullable=False)  # 积分阈值
    check_interval_minutes = Column(Integer, default=5, nullable=False)  # 检测间隔（分钟）
    current_member_id = Column(Integer, nullable=True)  # 当前使用的成员ID
    last_check_at = Column(DateTime, nullable=True)  # 上次检测时间
    last_switch_at = Column(DateTime, nullable=True)  # 上次切换时间
    switch_count = Column(Integer, default=0, nullable=False)  # 切换次数
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TeamMember(Base):
    """团队成员（固定Pro账号的成员列表）"""
    __tablename__ = "team_members"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, nullable=False, index=True)  # 关联的团队ID
    email = Column(String, nullable=False, index=True)  # 成员邮箱
    password = Column(String, nullable=False)  # 成员密码
    api_key = Column(String, nullable=True)  # 成员API Key
    name = Column(String, nullable=True)  # 成员名称
    is_enabled = Column(Boolean, default=False, nullable=False)  # 是否启用Windsurf访问
    is_current = Column(Boolean, default=False, nullable=False, index=True)  # 是否是当前使用的成员
    is_exhausted = Column(Boolean, default=False, nullable=False)  # 积分已用尽，不再切换回来
    last_credits = Column(Integer, default=0, nullable=False)  # 上次检测的积分
    last_check_at = Column(DateTime, nullable=True)  # 上次检测时间
    enabled_at = Column(DateTime, nullable=True)  # 启用时间
    disabled_at = Column(DateTime, nullable=True)  # 禁用时间
    sort_order = Column(Integer, default=0, nullable=False)  # 排序顺序
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class MemberSwitchHistory(Base):
    """成员切换历史记录"""
    __tablename__ = "member_switch_history"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, nullable=False, index=True)  # 团队ID
    from_member_id = Column(Integer, nullable=True)  # 原成员ID
    to_member_id = Column(Integer, nullable=False)  # 新成员ID
    from_email = Column(String, nullable=True)  # 原成员邮箱
    to_email = Column(String, nullable=False)  # 新成员邮箱
    reason = Column(String, nullable=False)  # 切换原因
    credits_before = Column(Integer, nullable=True)  # 切换前积分
    switched_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 切换时间
