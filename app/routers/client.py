from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
import math
import os

from app.database import get_db
from app.models import Account, ProAccount, Key, AccountStatus, KeyStatus, KeyType, Config, Announcement, VersionNote, PluginInfo, AccountAssignmentHistory, DeviceBinding, TeamLoginCache
from app.schemas import AccountGetResponse, KeyStatusResponse, VersionResponse, AnnouncementResponse, LoginRequest, LoginResponse, AccountHistoryResponse, AccountHistoryItem, VersionNotesResponse, VersionNoteItem, PluginInfoResponse, PluginVersionCheckResponse, PluginListResponse, PluginListItem, DeviceBindingListResponse, DeviceBindingItem, DeviceBindRequest, DeviceUnbindRequest, TeamSwitchResponse, ProSwitchResponse
from app.auth import get_api_key
from app.utils import calculate_remaining_time
from app.windsurf_login import windsurf_login

router = APIRouter(prefix="/api/client", tags=["客户端"])

# 从环境变量读取账号过期天数配置，默认为6天
ACCOUNT_EXPIRY_DAYS = int(os.getenv("ACCOUNT_EXPIRY_DAYS", "6"))

@router.post("/account/get", response_model=AccountGetResponse)
async def get_account(
    request: Request,
    api_key: str = Depends(get_api_key),
    device_id: str = None,  # 设备ID（可选，从请求头或body获取）
    db: Session = Depends(get_db)
):
    """
    客户端获取未使用账号
    - 需要在请求头中提供 X-API-Key
    - 支持设备绑定限制
    - 无限额度：5分钟限制 + 每日20次限制
    - 有限额度：按数量限制，无时间限制
    """
    # 验证密钥
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 检查是否被禁用
    if key.is_disabled:
        raise HTTPException(status_code=403, detail="密钥已被管理员禁用")
    
    # === 设备绑定验证 ===
    # 尝试从请求头获取设备ID
    if not device_id:
        device_id = request.headers.get("X-Device-ID")
    
    if device_id:
        # 查询该密钥的所有活跃设备绑定
        active_bindings = db.query(DeviceBinding).filter(
            DeviceBinding.key_code == api_key,
            DeviceBinding.is_active == True
        ).all()
        
        # 检查当前设备是否已绑定
        current_device_binding = next(
            (b for b in active_bindings if b.device_id == device_id),
            None
        )
        
        if current_device_binding:
            # 设备已绑定，更新最后活跃时间和请求次数
            current_device_binding.last_active_at = datetime.utcnow()
            current_device_binding.request_count += 1
            db.commit()
        else:
            # 设备未绑定，检查是否超过最大绑定数
            if len(active_bindings) >= key.max_devices:
                raise HTTPException(
                    status_code=403,
                    detail=f"设备绑定数已达上限（{key.max_devices}台），请先解绑其他设备"
                )
            
            # 创建新的设备绑定
            new_binding = DeviceBinding(
                key_code=api_key,
                device_id=device_id,
                device_name=request.headers.get("X-Device-Name"),
                first_bound_at=datetime.utcnow(),
                last_active_at=datetime.utcnow(),
                request_count=1,
                is_active=True
            )
            db.add(new_binding)
            db.commit()
    
    # 检查密钥状态（使用 UTC 时间）
    now = datetime.utcnow()
    today = date.today()
    
    # 调试日志：打印卡密类型
    print(f"🔍 [DEBUG] 卡密: {api_key[:8]}..., key_type: {key.key_type}, key_type.value: {key.key_type.value if hasattr(key.key_type, 'value') else key.key_type}")
    
    # 如果是首次使用，激活密钥
    if key.status == KeyStatus.inactive:
        key.status = KeyStatus.active
        key.activated_at = now
        # 计算过期时间：支持天数+小时数
        duration_hours = getattr(key, 'duration_hours', 0) or 0
        key.expires_at = now + timedelta(days=key.duration_days, hours=duration_hours)
        db.commit()
    
    # 检查是否过期
    if key.expires_at and now >= key.expires_at:
        if key.status != KeyStatus.expired:
            key.status = KeyStatus.expired
            db.commit()
        raise HTTPException(status_code=403, detail="密钥已过期")

    # === 根据密钥类型进行不同的限制 ===
    if key.key_type == KeyType.unlimited:
        # 无限额度：检查每日限制和频率限制
        
        # 1. 检查是否需要重置每日计数（零点重置）
        if key.last_reset_date != today:
            key.daily_request_count = 0
            key.last_reset_date = today
            db.commit()
        
        # 2. 检查每日限制（20次）
        if key.daily_request_count >= 20:
            raise HTTPException(
                status_code=429,
                detail="今日获取次数已达上限（20次），零点刷新"
            )
        
        # 3. 检查5分钟频率限制
        if key.last_request_at:
            time_since_last = (now - key.last_request_at).total_seconds()
            if time_since_last < 300:  # 5分钟 = 300秒
                wait_seconds = math.ceil(300 - time_since_last)
                raise HTTPException(
                    status_code=429,
                    detail=f"请求过于频繁，请{wait_seconds}秒后再试",
                    headers={"X-Retry-After": str(wait_seconds)}
                )
    
    elif key.key_type == KeyType.pro:
        # Pro类型：检查总额度限制（与limited相同），但只获取pro账号
        if key.account_limit == 0:
            raise HTTPException(status_code=403, detail="该密钥不包含账号配额")
        if key.account_limit > 0:
            remaining = max(key.account_limit - key.request_count, 0)
            if remaining <= 0:
                raise HTTPException(status_code=403, detail="密钥额度已用尽")
    
    else:  # limited 有限额度
        # 有限额度：检查总额度限制
        # account_limit = -1 表示不限制账号数量
        # account_limit = 0 表示不能获取账号（但密钥可用于插件授权）
        # account_limit > 0 表示固定配额
        if key.account_limit == 0:
            raise HTTPException(status_code=403, detail="该密钥不包含账号配额")
        if key.account_limit > 0:
            remaining = max(key.account_limit - key.request_count, 0)
            if remaining <= 0:
                raise HTTPException(status_code=403, detail="密钥额度已用尽")
        # account_limit == -1 时不检查配额，直接放行
    
    # === 获取账号 ===
    
    # 自动将创建时间超过指定天数的未使用账号设置为过期
    expiry_threshold = now - timedelta(days=ACCOUNT_EXPIRY_DAYS)
    expired_accounts = db.query(Account).filter(
        Account.status == AccountStatus.unused,
        Account.created_at < expiry_threshold
    ).update({Account.status: AccountStatus.expired}, synchronize_session=False)
    
    if expired_accounts > 0:
        db.commit()
    
    # Pro类型卡密特殊处理：返回固定的Pro账号（api_key从配置读取）
    if key.key_type == KeyType.pro:
        # 从配置表读取固定的Pro账号信息
        fixed_pro_email_config = db.query(Config).filter(Config.key == "fixed_pro_email").first()
        fixed_pro_name_config = db.query(Config).filter(Config.key == "fixed_pro_name").first()
        fixed_pro_api_key_config = db.query(Config).filter(Config.key == "fixed_pro_api_key").first()
        
        # 固定值（可在管理后台 Config 表中修改）
        fixed_email = fixed_pro_email_config.value if fixed_pro_email_config else "pro_user@windsurf.com"
        fixed_name = fixed_pro_name_config.value if fixed_pro_name_config else "ProUser"
        fixed_api_key = fixed_pro_api_key_config.value if fixed_pro_api_key_config else ""
        
        if not fixed_api_key:
            raise HTTPException(status_code=500, detail="Pro账号API Key未配置，请联系管理员")
        
        # 更新密钥统计
        key.request_count += 1
        key.last_request_at = now
        key.last_request_ip = request.client.host
        db.commit()
        
        # 直接返回固定的Pro账号信息
        return AccountGetResponse(
            email=fixed_email,
            api_key=fixed_api_key,
            name=fixed_name,
            is_pro=True
        )
    else:
        # 非Pro卡密：查询该密钥之前获取过的账号邮箱列表
        previously_assigned_emails = db.query(Account.email).filter(
            Account.assigned_to_key == api_key
        ).all()
        previously_assigned_emails = [email[0] for email in previously_assigned_emails]
        
        # 获取未使用的账号，排除该密钥之前获取过的账号，优先获取创建时间最久的
        # 普通卡密不能获取Pro账号
        query = db.query(Account).filter(
            Account.status == AccountStatus.unused,
            Account.is_pro == False
        )
        
        # 如果有之前获取过的账号，排除它们
        if previously_assigned_emails:
            query = query.filter(Account.email.notin_(previously_assigned_emails))
        
        account = query.order_by(Account.created_at.asc()).first()
    
    if not account:
        # 如果没有新账号了，检查是否所有账号都被该密钥使用过
        all_unused_count = db.query(Account).filter(
            Account.status == AccountStatus.unused
        ).count()
        
        if all_unused_count > 0:
            raise HTTPException(
                status_code=404, 
                detail="暂无新账号可用（所有未使用账号都已被该密钥获取过）"
            )
        else:
            raise HTTPException(status_code=404, detail="暂无可用账号")
    
    # 检查账号是否有 API Key，如果没有则自动登录获取
    # 使用循环尝试多个账号，如果账号被封禁则自动跳过
    max_retry = 5  # 最多尝试5个账号
    retry_count = 0
    
    while not account.api_key or account.api_key.strip() == '':
        try:
            # 通过登录获取 API Key (sk-ws-...)
            # use_short_term_key=True 使用 RegisterUser（推荐，更快）
            # use_short_term_key=False 使用 CreateTeamApiSecret（备用）
            login_result = await windsurf_login(
                email=account.email,
                password=account.password,
                db=db,
                use_short_term_key=True  # 使用 RegisterUser 获取
            )
            
            # 更新账号的 API Key
            account.api_key = login_result['api_key']
            # 如果名字为空，也更新名字
            if not account.name or account.name.strip() == '':
                account.name = login_result.get('name', '')
            
            db.commit()
            break  # 成功获取，跳出循环
            
        except Exception as e:
            error_msg = str(e)
            
            # 检查是否是账号被封禁/无效的错误
            invalid_account_keywords = ['invalid email', 'invalid_email', 'email_not_found', 'user_not_found', 'account_disabled', 'permission denied']
            if any(keyword in error_msg.lower() for keyword in invalid_account_keywords):
                # 将该账号标记为过期
                print(f"⚠️ 账号 {account.email} 已失效，自动标记为过期")
                account.status = AccountStatus.expired
                db.commit()
                
                retry_count += 1
                if retry_count >= max_retry:
                    raise HTTPException(
                        status_code=404,
                        detail=f"连续{max_retry}个账号登录失败，暂无可用账号"
                    )
                
                # 获取下一个账号
                if key.key_type == KeyType.pro:
                    # Pro卡密：随机获取另一个未使用的Pro账号
                    from sqlalchemy.sql.expression import func
                    query = db.query(ProAccount).filter(
                        ProAccount.status == AccountStatus.unused,  # 只获取未使用的账号
                        ProAccount.id != account.id  # 排除当前失败的账号
                    )
                    account = query.order_by(func.random()).first()
                else:
                    query = db.query(Account).filter(
                        Account.status == AccountStatus.unused,
                        Account.is_pro == False
                    )
                    if previously_assigned_emails:
                        query = query.filter(Account.email.notin_(previously_assigned_emails))
                    account = query.order_by(Account.created_at.asc()).first()
                
                if not account:
                    raise HTTPException(status_code=404, detail="暂无可用账号")
                continue  # 尝试下一个账号
            
            # 如果是账号池或额度相关的错误，明确提示
            if any(keyword in error_msg.lower() for keyword in ['quota', 'insufficient', '额度', '账号池', '账号不足']):
                raise HTTPException(
                    status_code=403,
                    detail="账号额度已用完，请购买新的额度"
                )
            # 其他登录失败错误
            raise HTTPException(
                status_code=403,
                detail=f"账号登录失败: {error_msg}"
            )
    
    # 更新账号状态为已使用
    account.status = AccountStatus.used
    account.assigned_at = now
    account.assigned_to_key = api_key
    
    # Pro卡密：同时记录到获取历史表
    if key.key_type == KeyType.pro:
        history_record = AccountAssignmentHistory(
            key_code=api_key,
            account_id=account.id,
            email=account.email,
            password=account.password,
            api_key=account.api_key,
            name=account.name,
            is_pro=True,
            assigned_at=now
        )
        db.add(history_record)
    
    # 更新密钥统计
    key.request_count += 1
    key.last_request_at = now
    key.last_request_ip = request.client.host
    
    # 无限额度：增加每日计数
    if key.key_type == KeyType.unlimited:
        key.daily_request_count += 1
    
    db.commit()
    
    # 根据密钥类型决定返回内容
    is_pro_account = key.key_type == KeyType.pro  # Pro账号来自 ProAccount 表
    response_data = {
        "email": account.email,
        "api_key": account.api_key,  # 长期API Key (sk-ws-...)
        "is_pro": is_pro_account
    }
    
    if key.key_type == KeyType.pro:
        # Pro类型：只返回名称，不返回密码
        response_data["name"] = account.name or account.email.split('@')[0]
    elif key.key_type == KeyType.limited:
        # 有限额度：返回密码
        response_data["password"] = account.password
    # 无限额度：不返回密码（前端显示 "PaperCrane"）
    
    return AccountGetResponse(**response_data)

@router.get("/key/status", response_model=KeyStatusResponse)
async def get_key_status(
    request: Request,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    查询密钥状态和剩余时间
    - 需要在请求头中提供 X-API-Key
    - 首次查询时自动激活密钥
    - 支持设备绑定限制
    """
    # 验证密钥
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 检查是否被禁用
    if key.is_disabled:
        raise HTTPException(status_code=403, detail="密钥已被管理员禁用")
    
    # === 设备绑定验证 ===
    device_id = request.headers.get("X-Device-ID")
    
    if device_id:
        # 查询该密钥的所有活跃设备绑定
        active_bindings = db.query(DeviceBinding).filter(
            DeviceBinding.key_code == api_key,
            DeviceBinding.is_active == True
        ).all()
        
        # 检查当前设备是否已绑定
        current_device_binding = next(
            (b for b in active_bindings if b.device_id == device_id),
            None
        )
        
        if current_device_binding:
            # 设备已绑定，更新最后活跃时间
            current_device_binding.last_active_at = datetime.utcnow()
            db.commit()
        else:
            # 设备未绑定，检查是否超过最大绑定数
            if len(active_bindings) >= key.max_devices:
                raise HTTPException(
                    status_code=403,
                    detail=f"设备绑定数已达上限（{key.max_devices}台），请先解绑其他设备"
                )
            
            # 创建新的设备绑定
            new_binding = DeviceBinding(
                key_code=api_key,
                device_id=device_id,
                device_name=request.headers.get("X-Device-Name"),
                first_bound_at=datetime.utcnow(),
                last_active_at=datetime.utcnow(),
                request_count=1,
                is_active=True
            )
            db.add(new_binding)
            db.commit()
    
    now = datetime.utcnow()
    
    # 如果是首次使用，激活密钥
    if key.status == KeyStatus.inactive:
        key.status = KeyStatus.active
        key.activated_at = now
        # 计算过期时间：支持天数+小时数
        duration_hours = getattr(key, 'duration_hours', 0) or 0
        key.expires_at = now + timedelta(days=key.duration_days, hours=duration_hours)
        db.commit()
    
    # 检查并更新过期状态
    if key.expires_at and now >= key.expires_at:
        if key.status != KeyStatus.expired:
            key.status = KeyStatus.expired
            db.commit()
    
    # 计算剩余时间
    remaining_time = calculate_remaining_time(key.expires_at)

    # 额度与剩余
    limit = key.account_limit or 0
    remaining_accounts = (max(limit - key.request_count, 0) if limit > 0 else -1)
    
    # 将 UTC 时间转换为本地时区（UTC+8）用于显示
    from datetime import timezone as tz
    from app.utils import CHINA_TZ
    UTC = tz.utc
    
    activated_at_local = None
    expires_at_local = None
    
    if key.activated_at:
        # naive datetime（UTC）-> aware datetime（UTC）-> 转换为 UTC+8
        activated_at_utc = key.activated_at.replace(tzinfo=UTC)
        activated_at_local = activated_at_utc.astimezone(CHINA_TZ)
    
    if key.expires_at:
        expires_at_utc = key.expires_at.replace(tzinfo=UTC)
        expires_at_local = expires_at_utc.astimezone(CHINA_TZ)
    
    return KeyStatusResponse(
        status=key.status.value,
        remaining_time=remaining_time,
        request_count=key.request_count,
        activated_at=activated_at_local,
        expires_at=expires_at_local,
        account_limit=limit,
        remaining_accounts=remaining_accounts,
        key_type=key.key_type.value  # 返回卡密类型
    )

@router.get("/version", response_model=VersionResponse)
async def check_version(
    client_version: str = "1.0.0",
    db: Session = Depends(get_db)
):
    """
    检查客户端版本是否需要更新
    - 返回当前服务器版本和最低支持的客户端版本
    - 如果客户端版本低于最低版本，返回 update_required=True
    """
    # 从配置表读取版本信息
    server_version_config = db.query(Config).filter(Config.key == "server_version").first()
    min_client_version_config = db.query(Config).filter(Config.key == "min_client_version").first()
    update_message_config = db.query(Config).filter(Config.key == "update_message").first()
    
    # 默认版本
    server_version = server_version_config.value if server_version_config else "1.0.0"
    min_client_version = min_client_version_config.value if min_client_version_config else "1.0.0"
    update_message = update_message_config.value if update_message_config else "发现新版本，请立即更新"
    
    # 简单的版本比较（假设格式为 x.y.z）
    def version_tuple(v):
        try:
            return tuple(map(int, v.split('.')))
        except:
            return (0, 0, 0)
    
    client_ver_tuple = version_tuple(client_version)
    min_ver_tuple = version_tuple(min_client_version)
    
    update_required = client_ver_tuple < min_ver_tuple
    
    return VersionResponse(
        version=server_version,
        min_client_version=min_client_version,
        update_required=update_required,
        update_message=update_message if update_required else None
    )

@router.get("/announcement", response_model=AnnouncementResponse)
async def get_announcement(db: Session = Depends(get_db)):
    """
    获取当前启用的公告
    - 公开接口，无需认证
    - 返回当前启用的公告内容
    - 如果没有启用的公告，返回空内容
    """
    try:
        # 查询启用的公告（按优先级和创建时间排序）
        announcement = db.query(Announcement).filter(
            Announcement.is_active == True
        ).order_by(
            Announcement.priority.desc(),
            Announcement.created_at.desc()
        ).first()
        
        if not announcement:
            # 没有启用的公告，返回空内容
            return AnnouncementResponse(content="")
        
        return AnnouncementResponse(
            content=announcement.content,
            created_at=announcement.created_at.isoformat() if announcement.created_at else None,
            updated_at=announcement.updated_at.isoformat() if announcement.updated_at else None
        )
    except Exception as e:
        # 出错时返回空内容，不影响客户端使用
        return AnnouncementResponse(content="")

@router.post("/login", response_model=LoginResponse)
async def login_with_account(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    通过账号密码登录并获取 API Key
    - 公开接口，无需认证
    - 自动通过 Firebase 和 Windsurf API 获取 API Key
    - 如果账号已存在则返回现有信息，否则创建新账号
    """
    try:
        # 检查账号是否已存在
        existing_account = db.query(Account).filter(
            Account.email == login_data.email
        ).first()
        
        if existing_account:
            # 账号已存在，直接返回
            return LoginResponse(
                success=True,
                message="登录成功（使用已有账号）",
                data={
                    "email": existing_account.email,
                    "api_key": existing_account.api_key,
                    "name": existing_account.name,
                    "status": existing_account.status.value,
                    "created_at": existing_account.created_at.isoformat()
                }
            )
        
        # 账号不存在，通过模拟登录获取 API Key
        try:
            result = await windsurf_login(
                email=login_data.email,
                password=login_data.password,
                db=db
            )
            
            # 创建新账号
            new_account = Account(
                email=result['email'],
                password=result['password'],
                api_key=result['api_key'],
                name=result['name'],
                status=AccountStatus.unused,
                created_at=datetime.utcnow()
            )
            
            db.add(new_account)
            db.commit()
            db.refresh(new_account)
            
            return LoginResponse(
                success=True,
                message="登录成功并创建新账号",
                data={
                    "email": new_account.email,
                    "api_key": new_account.api_key,
                    "name": new_account.name,
                    "status": new_account.status.value,
                    "created_at": new_account.created_at.isoformat()
                }
            )
        
        except Exception as login_error:
            return LoginResponse(
                success=False,
                message=f"登录失败: {str(login_error)}",
                data=None
            )
    
    except Exception as e:
        return LoginResponse(
            success=False,
            message=f"处理请求失败: {str(e)}",
            data=None
        )

@router.get("/account/history", response_model=AccountHistoryResponse)
async def get_account_history(
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    获取该密钥关联的所有账号历史
    - 需要在请求头中提供 X-API-Key
    - 返回该密钥曾经获取过的所有账号（包含密码）
    - 同时查询普通账号和Pro账号历史
    """
    # 验证密钥
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 检查是否被禁用
    if key.is_disabled:
        raise HTTPException(status_code=403, detail="密钥已被管理员禁用")
    
    try:
        account_list = []
        
        # 1. 查询普通账号（通过 assigned_to_key 关联，排除Pro账号避免重复）
        normal_accounts = db.query(Account).filter(
            Account.assigned_to_key == api_key,
            Account.is_pro == False  # 排除Pro账号，Pro账号在历史表中查询
        ).order_by(Account.assigned_at.desc()).all()
        
        for acc in normal_accounts:
            account_list.append(AccountHistoryItem(
                email=acc.email,
                password=acc.password,
                api_key=acc.api_key,
                name=acc.name,
                assigned_at=acc.assigned_at,
                is_pro=False  # 普通账号
            ))
        
        # 2. 查询Pro账号历史（通过历史表）
        pro_history = db.query(AccountAssignmentHistory).filter(
            AccountAssignmentHistory.key_code == api_key
        ).order_by(AccountAssignmentHistory.assigned_at.desc()).all()
        
        for hist in pro_history:
            account_list.append(AccountHistoryItem(
                email=hist.email,
                password=None,  # Pro账号不返回密码
                api_key=hist.api_key,
                name=hist.name,  # Pro账号显示名称
                account_id=hist.account_id,  # Pro账号显示ID
                assigned_at=hist.assigned_at,
                is_pro=True  # Pro账号
            ))
        
        # 按时间降序排序（合并后重新排序）
        account_list.sort(key=lambda x: x.assigned_at if x.assigned_at else datetime.min, reverse=True)
        
        return AccountHistoryResponse(
            success=True,
            message=f"获取成功，共 {len(account_list)} 个账号",
            accounts=account_list,
            total=len(account_list)
        )
    except Exception as e:
        return AccountHistoryResponse(
            success=False,
            message=f"获取账号历史失败: {str(e)}",
            accounts=[],
            total=0
        )

@router.get("/version-notes", response_model=VersionNotesResponse)
async def get_version_notes(db: Session = Depends(get_db)):
    """
    获取已发布的版本说明列表
    - 公开接口，无需认证
    - 按版本号降序排列
    """
    try:
        notes = db.query(VersionNote).filter(
            VersionNote.is_published == True
        ).order_by(VersionNote.release_date.desc()).all()
        
        note_list = [
            VersionNoteItem(
                id=note.id,
                version=note.version,
                title=note.title,
                content=note.content,
                release_date=note.release_date,
                is_published=note.is_published,
                created_at=note.created_at,
                updated_at=note.updated_at
            )
            for note in notes
        ]
        
        return VersionNotesResponse(
            success=True,
            message=f"获取成功，共 {len(note_list)} 条版本说明",
            notes=note_list,
            total=len(note_list)
        )
    except Exception as e:
        return VersionNotesResponse(
            success=False,
            message=f"获取版本说明失败: {str(e)}",
            notes=[],
            total=0
        )


@router.get("/plugin/list", response_model=PluginListResponse)
async def get_plugin_list(db: Session = Depends(get_db)):
    """
    获取插件列表
    - 公开接口，无需认证
    - 返回所有启用的插件信息，包含完整的客户端展示字段
    """
    try:
        plugins = db.query(PluginInfo).filter(
            PluginInfo.is_active == True
        ).order_by(PluginInfo.sort_order, PluginInfo.id).all()
        
        plugin_items = [
            PluginListItem(
                name=p.plugin_name,
                display_name=p.display_name or p.plugin_name.replace("-", " ").title(),
                description=p.description or p.update_description or "",
                ide_type=p.ide_type or "windsurf",
                latest_version=p.current_version,
                download_url=p.download_url,
                is_primary=p.is_primary,
                icon=p.icon or "shield-check",
                icon_gradient=p.icon_gradient,
                features=p.features,
                usage_steps=p.usage_steps,
                tips=p.tips,
                mcp_config_path=p.mcp_config_path,
                extensions_path=p.extensions_path,
                mcp_extra_config=p.mcp_extra_config,
                sort_order=p.sort_order
            )
            for p in plugins
        ]
        
        return PluginListResponse(success=True, plugins=plugin_items)
    except Exception:
        return PluginListResponse(success=False, plugins=[])


@router.get("/plugin/info", response_model=PluginInfoResponse)
async def get_plugin_info(
    plugin_name: str = "windsurf-continue-pro",
    db: Session = Depends(get_db)
):
    """
    获取插件信息
    - 公开接口，无需认证
    - 返回插件的最新版本、下载地址等信息
    """
    plugin = db.query(PluginInfo).filter(
        PluginInfo.plugin_name == plugin_name,
        PluginInfo.is_active == True
    ).first()
    
    if not plugin:
        raise HTTPException(status_code=404, detail=f"未找到插件: {plugin_name}")
    
    return PluginInfoResponse(
        plugin_name=plugin.plugin_name,
        current_version=plugin.current_version,
        min_version=plugin.min_version,
        download_url=plugin.download_url,
        changelog=plugin.changelog,
        update_title=plugin.update_title,
        update_description=plugin.update_description,
        is_force_update=plugin.is_force_update,
        file_size=plugin.file_size,
        release_date=plugin.release_date
    )


@router.get("/plugin/check-update", response_model=PluginVersionCheckResponse)
async def check_plugin_update(
    plugin_name: str = "windsurf-continue-pro",
    client_version: str = "1.0.0",
    db: Session = Depends(get_db)
):
    """
    检查插件是否需要更新
    - 公开接口，无需认证
    - 比较客户端版本和服务器版本
    - 返回是否有更新、是否强制更新等信息
    """
    plugin = db.query(PluginInfo).filter(
        PluginInfo.plugin_name == plugin_name,
        PluginInfo.is_active == True
    ).first()
    
    if not plugin:
        # 未找到插件信息，返回无更新
        return PluginVersionCheckResponse(
            has_update=False,
            is_force_update=False,
            current_version=client_version,
            latest_version=client_version
        )
    
    # 版本比较函数
    def version_tuple(v):
        try:
            return tuple(map(int, v.split('.')))
        except:
            return (0, 0, 0)
    
    client_ver = version_tuple(client_version)
    server_ver = version_tuple(plugin.current_version)
    min_ver = version_tuple(plugin.min_version) if plugin.min_version else (0, 0, 0)
    
    has_update = client_ver < server_ver
    # 如果客户端版本低于最低版本，或者设置了强制更新，则强制更新
    is_force = (client_ver < min_ver) or (has_update and plugin.is_force_update)
    
    return PluginVersionCheckResponse(
        has_update=has_update,
        is_force_update=is_force,
        current_version=client_version,
        latest_version=plugin.current_version,
        download_url=plugin.download_url if has_update else None,
        update_title=plugin.update_title if has_update else None,
        update_description=plugin.update_description if has_update else None,
        changelog=plugin.changelog if has_update else None,
        file_size=plugin.file_size if has_update else None
    )


@router.get("/device/list", response_model=DeviceBindingListResponse)
async def get_device_bindings(
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    获取该密钥的所有设备绑定
    - 需要在请求头中提供 X-API-Key
    - 返回所有已绑定的设备列表
    """
    # 验证密钥
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 查询所有活跃的设备绑定
    bindings = db.query(DeviceBinding).filter(
        DeviceBinding.key_code == api_key,
        DeviceBinding.is_active == True
    ).order_by(DeviceBinding.last_active_at.desc()).all()
    
    device_items = [
        DeviceBindingItem(
            id=b.id,
            device_id=b.device_id,
            device_name=b.device_name,
            first_bound_at=b.first_bound_at,
            last_active_at=b.last_active_at,
            request_count=b.request_count,
            is_active=b.is_active
        )
        for b in bindings
    ]
    
    return DeviceBindingListResponse(
        success=True,
        message=f"获取成功，共 {len(device_items)} 台设备",
        devices=device_items,
        total=len(device_items),
        max_devices=key.max_devices
    )


@router.post("/device/unbind")
async def unbind_device(
    unbind_data: DeviceUnbindRequest,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    解绑指定设备
    - 需要在请求头中提供 X-API-Key
    - 将设备标记为非活跃状态
    """
    # 验证密钥
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 查找设备绑定
    binding = db.query(DeviceBinding).filter(
        DeviceBinding.key_code == api_key,
        DeviceBinding.device_id == unbind_data.device_id,
        DeviceBinding.is_active == True
    ).first()
    
    if not binding:
        raise HTTPException(status_code=404, detail="未找到该设备绑定")
    
    # 标记为非活跃
    binding.is_active = False
    db.commit()
    
    return {
        "success": True,
        "message": "设备解绑成功"
    }


@router.post("/team/switch", response_model=TeamSwitchResponse)
async def team_switch_account(
    request: Request,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Team卡密一键切号
    - 需要在请求头中提供 X-API-Key
    - 仅支持 team 类型卡密
    - 调用第三方API获取登录URL，缓存10分钟
    """
    import httpx
    
    # 固定机器码（测试成功的机器码）
    FIXED_MACHINE_ID = "76fcc3e5a35ba30dafaccdc471d87907b367b31fa3206197945142097b9caa58"
    
    # 验证密钥
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 检查是否被禁用
    if key.is_disabled:
        raise HTTPException(status_code=403, detail="密钥已被管理员禁用")
    
    # 检查密钥类型
    if key.key_type != KeyType.team:
        raise HTTPException(status_code=403, detail="该密钥不支持一键切号功能，仅Team卡密可用")
    
    # 检查是否配置了第三方卡密
    if not key.team_card_key:
        raise HTTPException(status_code=403, detail="该密钥未配置Team卡密")
    
    now = datetime.utcnow()
    
    # 如果是首次使用，激活密钥
    if key.status == KeyStatus.inactive:
        key.status = KeyStatus.active
        key.activated_at = now
        # 计算过期时间：支持天数+小时数
        duration_hours = getattr(key, 'duration_hours', 0) or 0
        key.expires_at = now + timedelta(days=key.duration_days, hours=duration_hours)
        db.commit()
    
    # 检查是否过期
    if key.expires_at and now >= key.expires_at:
        if key.status != KeyStatus.expired:
            key.status = KeyStatus.expired
            db.commit()
        raise HTTPException(status_code=403, detail="密钥已过期")
    
    # === 检查缓存（已禁用，每次获取新URL） ===
    cache = db.query(TeamLoginCache).filter(
        TeamLoginCache.key_code == api_key
    ).first()
    
    # 缓存有效期设为0，每次都获取新URL（OTT是一次性的）
    # if cache and cache.expires_at > now:
    #     # 缓存有效，直接返回
    #     expires_in = int((cache.expires_at - now).total_seconds())
    #     
    #     # 更新统计
    #     key.request_count += 1
    #     key.last_request_at = now
    #     key.last_request_ip = request.client.host
    #     db.commit()
    #     
    #     return TeamSwitchResponse(
    #         success=True,
    #         message="获取成功（缓存）",
    #         callback_url=cache.callback_url,
    #         email=cache.email,
    #         nickname=cache.nickname,
    #         cached=True,
    #         expires_in=expires_in
    #     )
    
    # === 缓存过期或不存在，调用第三方API ===
    try:
        # 使用固定机器码
        machine_id = FIXED_MACHINE_ID
        
        # 调用第三方API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://windsurf.aomanoh.com/api/v1/get-login-url",
                json={
                    "card_key": key.team_card_key,
                    "machine_id": machine_id
                },
                headers={"Content-Type": "application/json"}
            )
            
            result = response.json()
            
            if result.get("code") != 0:
                error_msg = result.get("message", "第三方API调用失败")
                return TeamSwitchResponse(
                    success=False,
                    message=f"切号失败: {error_msg}"
                )
            
            data = result.get("data", {})
            callback_url = data.get("callback_url", "")
            email = data.get("email", "")
            nickname = data.get("nickname", "")
            
            if not callback_url:
                return TeamSwitchResponse(
                    success=False,
                    message="获取登录URL失败"
                )
            
            # 注意：OTT 无法通过 API 直接转换为有效的 API Key
            # 必须让 Windsurf 客户端通过 URI Handler 处理
            # 客户端流程：打开 callback_url -> Windsurf 处理 -> 从数据库读取新 API Key
            
            # === 更新或创建缓存（有效期设为0，实际不使用缓存） ===
            cache_expires_at = now  # 立即过期，每次都获取新URL
            
            if cache:
                cache.team_card_key = key.team_card_key
                cache.callback_url = callback_url
                cache.email = email
                cache.nickname = nickname
                cache.cached_at = now
                cache.expires_at = cache_expires_at
            else:
                cache = TeamLoginCache(
                    key_code=api_key,
                    team_card_key=key.team_card_key,
                    callback_url=callback_url,
                    email=email,
                    nickname=nickname,
                    cached_at=now,
                    expires_at=cache_expires_at
                )
                db.add(cache)
            
            # 更新统计
            key.request_count += 1
            key.last_request_at = now
            key.last_request_ip = request.client.host
            db.commit()
            
            return TeamSwitchResponse(
                success=True,
                message="获取成功",
                callback_url=callback_url,
                api_key=None,  # OTT 无法直接转换，需客户端通过 URI Handler 处理
                email=email,
                nickname=nickname,
                cached=False,
                expires_in=600  # 10分钟
            )
            
    except httpx.TimeoutException:
        return TeamSwitchResponse(
            success=False,
            message="第三方API请求超时"
        )
    except Exception as e:
        return TeamSwitchResponse(
            success=False,
            message=f"切号失败: {str(e)}"
        )


@router.post("/pro/switch", response_model=ProSwitchResponse)
async def pro_switch_account(
    request: Request,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Pro卡密一键切号（无感换号）
    - 需要在请求头中提供 X-API-Key
    - 仅支持 pro 类型卡密
    - **自动检测积分并切换成员**（如果配置了团队）
    - 使用固定 Pro 账号的账号密码登录获取 api_key
    - 返回 callback_url 供客户端触发无感换号
    """
    import urllib.parse
    
    # 验证密钥
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 检查是否被禁用
    if key.is_disabled:
        raise HTTPException(status_code=403, detail="密钥已被管理员禁用")
    
    # 检查密钥类型（仅 pro 类型可用）
    if key.key_type != KeyType.pro:
        raise HTTPException(status_code=403, detail="该密钥不支持Pro一键切号功能，仅Pro卡密可用")
    
    now = datetime.utcnow()
    
    # === 频率限制：防止接口被恶意刷调用 ===
    # Pro切号接口限制：每30秒最多调用1次（使用独立的时间戳字段）
    PRO_SWITCH_COOLDOWN = 30  # 秒
    if key.last_pro_switch_at:
        time_since_last = (now - key.last_pro_switch_at).total_seconds()
        if time_since_last < PRO_SWITCH_COOLDOWN:
            wait_seconds = math.ceil(PRO_SWITCH_COOLDOWN - time_since_last)
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，请等待 {wait_seconds} 秒后再试"
            )
    
    # 如果是首次使用，激活密钥
    if key.status == KeyStatus.inactive:
        key.status = KeyStatus.active
        key.activated_at = now
        # 计算过期时间：支持天数+小时数
        duration_hours = getattr(key, 'duration_hours', 0) or 0
        key.expires_at = now + timedelta(days=key.duration_days, hours=duration_hours)
        db.commit()
    
    # 检查是否过期
    if key.expires_at and now >= key.expires_at:
        if key.status != KeyStatus.expired:
            key.status = KeyStatus.expired
            db.commit()
        raise HTTPException(status_code=403, detail="密钥已过期")
    
    # 检查额度限制
    if key.account_limit == 0:
        raise HTTPException(status_code=403, detail="该密钥不包含账号配额")
    if key.account_limit > 0:
        remaining = max(key.account_limit - key.request_count, 0)
        if remaining <= 0:
            raise HTTPException(status_code=403, detail="密钥额度已用尽")
    
    try:
        # ========== 积分检测与自动切换 ==========
        # 通过卡密的team_id查找关联的团队配置
        team = None
        switch_info = None
        skip_credits_check = False
        
        # 检查是否在切换冷却期内（1分钟）
        SWITCH_COOLDOWN_SECONDS = 60  # 切换后1分钟内不再检测积分
        if key.team_id:
            team = db.query(TeamConfig).filter(TeamConfig.id == key.team_id).first()
            if team and team.last_switch_at:
                time_since_switch = (now - team.last_switch_at).total_seconds()
                if time_since_switch < SWITCH_COOLDOWN_SECONDS:
                    skip_credits_check = True
                    print(f"⏱️ [Pro切号] 在切换冷却期内 ({int(time_since_switch)}秒/{SWITCH_COOLDOWN_SECONDS}秒)，跳过积分检测")
        
        if team and not skip_credits_check:
            print(f"📊 [Pro切号] 检测到团队配置: {team.name} (team_id={key.team_id})")
            # 执行积分检测和自动切换
            switch_info = await _check_and_switch_member(db, team)
            if switch_info:
                print(f"🔄 [Pro切号] 成员切换: {switch_info.get('message', '')}")
        
        # 从配置表读取固定的 Pro 账号信息（账号密码）
        # 注意：如果刚刚执行了切换，配置已经更新为新成员的账号
        fixed_pro_email_config = db.query(Config).filter(Config.key == "fixed_pro_email").first()
        fixed_pro_password_config = db.query(Config).filter(Config.key == "fixed_pro_password").first()
        fixed_pro_name_config = db.query(Config).filter(Config.key == "fixed_pro_name").first()
        
        fixed_email = fixed_pro_email_config.value if fixed_pro_email_config else None
        fixed_password = fixed_pro_password_config.value if fixed_pro_password_config else None
        fixed_name = fixed_pro_name_config.value if fixed_pro_name_config else "ProUser"
        
        if not fixed_email or not fixed_password:
            missing = []
            if not fixed_email:
                missing.append("fixed_pro_email")
            if not fixed_password:
                missing.append("fixed_pro_password")
            return ProSwitchResponse(
                success=False,
                message=f"Pro账号配置不完整，缺少: {', '.join(missing)}。请在管理后台【设置-Pro账号配置】中配置"
            )
        
        # 通过账号密码登录获取 OTT Token（用于无感换号）
        print(f"🔐 [Pro切号] 开始登录 Pro 账号: {fixed_email}")
        
        from app.windsurf_login import WindsurfLoginService
        login_service = WindsurfLoginService(db=db)
        
        try:
            # 尝试获取 OTT Token（用于无感换号）
            ott_result = await login_service.get_ott_token(
                email=fixed_email,
                password=fixed_password
            )
            
            ott_token = ott_result.get('ott_token')
            token_type = ott_result.get('token_type', 'unknown')
            result_name = ott_result.get('name', fixed_name)
            
            if not ott_token:
                return ProSwitchResponse(
                    success=False,
                    message="登录成功但未获取到 Token"
                )
            
            print(f"✅ [Pro切号] 获取 Token 成功: {ott_token[:30]}... (类型: {token_type})")
            
            # 构造 callback_url（无感换号 URL）
            # 格式: windsurf://codeium.windsurf#access_token=xxx&state=xxx&token_type=Bearer
            state = f"pro_switch_{int(now.timestamp())}"
            callback_url = f"windsurf://codeium.windsurf#access_token={urllib.parse.quote(ott_token)}&state={state}&token_type=Bearer"
            
            print(f"🔗 [Pro切号] 构造 callback_url: {callback_url[:80]}...")
            
            # 更新密钥统计
            key.request_count += 1
            key.last_request_at = now
            key.last_pro_switch_at = now  # 更新Pro切号专用时间戳
            key.last_request_ip = request.client.host
            db.commit()
            
            return ProSwitchResponse(
                success=True,
                message=f"获取成功 (Token类型: {token_type})",
                callback_url=callback_url,
                api_key=ott_token,
                token_type=token_type,
                email=fixed_email,
                name=result_name
            )
            
        finally:
            await login_service.close()
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ [Pro切号] 失败: {error_msg}")
        return ProSwitchResponse(
            success=False,
            message=f"Pro切号失败: {error_msg}"
        )


# ==================== 脚本专用接口 ====================

# 脚本更新 API Key 的密钥（可以在环境变量中配置，留空则不验证）
SCRIPT_UPDATE_SECRET = os.getenv("SCRIPT_UPDATE_SECRET", "")

@router.post("/update-pro-api-key")
async def update_pro_api_key(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    脚本专用接口：更新固定 Pro 账号的 API Key
    
    请求体 JSON:
    {
        "secret": "脚本密钥（如果后端配置了则必填）",
        "api_key": "新的 API Key (sk-ws-...)",
        "email": "可选，账号邮箱"
    }
    """
    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="无效的 JSON 数据")
    
    # 验证脚本密钥（如果配置了密钥则验证，否则跳过）
    if SCRIPT_UPDATE_SECRET:
        secret = data.get("secret", "")
        if secret != SCRIPT_UPDATE_SECRET:
            raise HTTPException(status_code=401, detail="无效的脚本密钥")
    
    api_key = data.get("api_key", "").strip()
    email = data.get("email", "").strip()
    
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    
    if not api_key.startswith("sk-ws-"):
        raise HTTPException(status_code=400, detail="API Key 格式不正确，必须以 sk-ws- 开头")
    
    # 更新 fixed_pro_api_key
    config = db.query(Config).filter(Config.key == "fixed_pro_api_key").first()
    if config:
        old_key = config.value
        config.value = api_key
    else:
        old_key = None
        db.add(Config(key="fixed_pro_api_key", value=api_key))
    
    # 如果提供了邮箱，也更新
    if email:
        email_config = db.query(Config).filter(Config.key == "fixed_pro_email").first()
        if email_config:
            email_config.value = email
        else:
            db.add(Config(key="fixed_pro_email", value=email))
    
    db.commit()
    
    # 记录日志
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] 脚本更新 Pro API Key: {api_key[:30]}... (来自: {request.client.host})")
    
    return {
        "success": True,
        "message": "Pro API Key 已更新",
        "old_key": old_key[:30] + "..." if old_key else None,
        "new_key": api_key[:30] + "...",
        "email": email or None
    }


# ==================== 团队成员管理（固定Pro账号积分检测与自动切换） ====================

from app.models import TeamConfig, TeamMember, MemberSwitchHistory
from app.schemas import (
    TeamConfigCreate, TeamConfigUpdate, TeamConfigResponse,
    TeamMemberCreate, TeamMemberUpdate, TeamMemberResponse,
    TeamListResponse, TeamMemberListResponse, TeamSwitchHistoryListResponse,
    TeamAutoSwitchResponse, TeamCreditsCheckResponse, MemberSwitchHistoryResponse
)

@router.get("/team/list", response_model=TeamListResponse)
async def get_team_list(
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """获取当前密钥关联的团队"""
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 通过key.team_id获取关联的团队
    teams = []
    if key.team_id:
        team = db.query(TeamConfig).filter(TeamConfig.id == key.team_id).first()
        if team:
            teams = [team]
    
    return TeamListResponse(
        success=True,
        teams=[TeamConfigResponse.model_validate(t) for t in teams],
        total=len(teams)
    )


@router.post("/team/create", response_model=TeamConfigResponse)
async def create_team(
    data: TeamConfigCreate,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """创建团队配置（团队创建后需要在后台将卡密关联到团队）"""
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 检查是否已存在同名团队
    existing = db.query(TeamConfig).filter(
        TeamConfig.name == data.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已存在同名团队")
    
    team = TeamConfig(
        name=data.name,
        admin_email=data.admin_email,
        admin_password=data.admin_password,
        credits_threshold=data.credits_threshold,
        check_interval_minutes=data.check_interval_minutes
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    
    # 自动关联到当前卡密
    key.team_id = team.id
    db.commit()
    
    return TeamConfigResponse.model_validate(team)


@router.put("/team/{team_id}", response_model=TeamConfigResponse)
async def update_team(
    team_id: int,
    data: TeamConfigUpdate,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """更新团队配置"""
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    if data.name is not None:
        team.name = data.name
    if data.admin_email is not None:
        team.admin_email = data.admin_email
    if data.admin_password is not None:
        team.admin_password = data.admin_password
    if data.credits_threshold is not None:
        team.credits_threshold = data.credits_threshold
    if data.check_interval_minutes is not None:
        team.check_interval_minutes = data.check_interval_minutes
    if data.is_active is not None:
        team.is_active = data.is_active
    
    db.commit()
    db.refresh(team)
    return TeamConfigResponse.model_validate(team)


@router.delete("/team/{team_id}")
async def delete_team(
    team_id: int,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """删除团队及其所有成员"""
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    # 删除团队成员
    db.query(TeamMember).filter(TeamMember.team_id == team_id).delete()
    # 删除切换历史
    db.query(MemberSwitchHistory).filter(MemberSwitchHistory.team_id == team_id).delete()
    # 删除团队
    db.delete(team)
    db.commit()
    
    return {"success": True, "message": "团队已删除"}


@router.get("/team/{team_id}/members", response_model=TeamMemberListResponse)
async def get_team_members(
    team_id: int,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """获取团队成员列表"""
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    members = db.query(TeamMember).filter(
        TeamMember.team_id == team_id
    ).order_by(TeamMember.sort_order).all()
    
    return TeamMemberListResponse(
        success=True,
        members=[TeamMemberResponse.model_validate(m) for m in members],
        total=len(members)
    )


@router.post("/team/{team_id}/members", response_model=TeamMemberResponse)
async def add_team_member(
    team_id: int,
    data: TeamMemberCreate,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """添加团队成员"""
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    # 检查邮箱是否已存在
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.email == data.email
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该成员已存在")
    
    member = TeamMember(
        team_id=team_id,
        email=data.email,
        password=data.password,
        name=data.name,
        sort_order=data.sort_order
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    
    return TeamMemberResponse.model_validate(member)


@router.put("/team/{team_id}/members/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    team_id: int,
    member_id: int,
    data: TeamMemberUpdate,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """更新团队成员"""
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.team_id == team_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 验证团队归属
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    if data.email is not None:
        member.email = data.email
    if data.password is not None:
        member.password = data.password
    if data.name is not None:
        member.name = data.name
    if data.sort_order is not None:
        member.sort_order = data.sort_order
    
    db.commit()
    db.refresh(member)
    return TeamMemberResponse.model_validate(member)


@router.delete("/team/{team_id}/members/{member_id}")
async def delete_team_member(
    team_id: int,
    member_id: int,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """删除团队成员"""
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.team_id == team_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 验证团队归属
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    db.delete(member)
    db.commit()
    
    return {"success": True, "message": "成员已删除"}


@router.get("/team/{team_id}/history", response_model=TeamSwitchHistoryListResponse)
async def get_switch_history(
    team_id: int,
    limit: int = 50,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """获取成员切换历史"""
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    history = db.query(MemberSwitchHistory).filter(
        MemberSwitchHistory.team_id == team_id
    ).order_by(MemberSwitchHistory.switched_at.desc()).limit(limit).all()
    
    return TeamSwitchHistoryListResponse(
        success=True,
        history=[MemberSwitchHistoryResponse.model_validate(h) for h in history],
        total=len(history)
    )


@router.post("/team/{team_id}/auto-switch", response_model=TeamAutoSwitchResponse)
async def auto_switch_member(
    team_id: int,
    threshold: int = None,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    自动切换成员
    - 检测当前成员积分，如果低于阈值则自动切换到下一个可用成员
    - 调用Windsurf API禁用当前成员，启用新成员
    - 更新固定Pro账号配置
    """
    from app.windsurf_api import update_codeium_access, login_with_email, refresh_token
    
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    # 使用传入的阈值或团队配置的阈值
    credits_threshold = threshold if threshold is not None else team.credits_threshold
    
    # 确保管理员Token有效
    admin_token = await _ensure_admin_token(db, team)
    if not admin_token:
        return TeamAutoSwitchResponse(
            success=False,
            message="无法获取管理员Token，请检查管理员账号配置"
        )
    
    # 获取当前成员
    current_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.is_current == True
    ).first()
    
    # 如果没有当前成员，选择第一个成员
    if not current_member:
        members = db.query(TeamMember).filter(
            TeamMember.team_id == team_id
        ).order_by(TeamMember.sort_order).all()
        
        if not members:
            return TeamAutoSwitchResponse(
                success=False,
                message="没有可用的成员"
            )
        
        # 设置第一个成员为当前成员
        current_member = members[0]
        
        # 调用Windsurf API启用该成员
        if current_member.api_key:
            enable_result = await update_codeium_access(admin_token, current_member.api_key, False)
            if not enable_result.get("success"):
                print(f"⚠️ [TeamSwitch] 启用成员失败: {enable_result.get('error', 'unknown')}")
        
        current_member.is_current = True
        current_member.is_enabled = True
        current_member.enabled_at = datetime.utcnow()
        team.current_member_id = current_member.id
        db.commit()
        
        # 更新固定Pro账号配置
        _update_fixed_pro_config(db, current_member.email, current_member.password)
        
        return TeamAutoSwitchResponse(
            success=True,
            message="已设置初始成员",
            switched=True,
            to_member=current_member.email,
            new_email=current_member.email,
            new_password=current_member.password,
            reason="初始化"
        )
    
    # 检测当前成员积分
    current_credits = current_member.last_credits
    
    # 更新检测时间
    current_member.last_check_at = datetime.utcnow()
    team.last_check_at = datetime.utcnow()
    
    # 判断是否需要切换
    if current_credits >= credits_threshold:
        db.commit()
        return TeamAutoSwitchResponse(
            success=True,
            message=f"当前积分 {current_credits} 高于阈值 {credits_threshold}，无需切换",
            switched=False,
            current_credits=current_credits
        )
    
    # 需要切换，查找下一个可用成员（跳过已用尽的成员）
    members = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.id != current_member.id,
        TeamMember.is_exhausted == False  # 跳过已用尽的成员
    ).order_by(TeamMember.sort_order).all()
    
    # 查找未启用的成员（有api_key的优先）
    next_member = None
    for m in members:
        if not m.is_enabled:
            next_member = m
            break
    
    if not next_member:
        db.commit()
        return TeamAutoSwitchResponse(
            success=False,
            message="没有可用的成员可切换",
            switched=False,
            current_credits=current_credits
        )
    
    # 执行切换 - 调用Windsurf API
    # 1. 禁用当前成员的Windsurf访问
    if current_member.api_key:
        disable_result = await update_codeium_access(admin_token, current_member.api_key, True)
        if disable_result.get("success"):
            print(f"✅ [TeamSwitch] 已禁用成员: {current_member.email}")
        else:
            print(f"⚠️ [TeamSwitch] 禁用成员失败: {disable_result.get('error', 'unknown')}")
    
    # 2. 启用新成员的Windsurf访问
    if next_member.api_key:
        enable_result = await update_codeium_access(admin_token, next_member.api_key, False)
        if enable_result.get("success"):
            print(f"✅ [TeamSwitch] 已启用成员: {next_member.email}")
        else:
            print(f"⚠️ [TeamSwitch] 启用成员失败: {enable_result.get('error', 'unknown')}")
    
    # 3. 更新数据库状态
    current_member.is_current = False
    current_member.is_enabled = False
    current_member.is_exhausted = True  # 标记为已用尽
    current_member.disabled_at = datetime.utcnow()
    
    next_member.is_current = True
    next_member.is_enabled = True
    next_member.enabled_at = datetime.utcnow()
    
    # 4. 更新团队配置
    team.current_member_id = next_member.id
    team.last_switch_at = datetime.utcnow()
    team.switch_count += 1
    
    # 5. 记录切换历史
    history = MemberSwitchHistory(
        team_id=team_id,
        from_member_id=current_member.id,
        to_member_id=next_member.id,
        from_email=current_member.email,
        to_email=next_member.email,
        reason=f"积分低于阈值 ({current_credits} < {credits_threshold})",
        credits_before=current_credits
    )
    db.add(history)
    
    # 6. 更新固定Pro账号配置
    _update_fixed_pro_config(db, next_member.email, next_member.password)
    
    db.commit()
    
    print(f"🔄 [TeamSwitch] 成员切换完成: {current_member.email} -> {next_member.email} (积分: {current_credits})")
    
    return TeamAutoSwitchResponse(
        success=True,
        message=f"成员已切换",
        switched=True,
        from_member=current_member.email,
        to_member=next_member.email,
        new_email=next_member.email,
        new_password=next_member.password,
        reason=f"积分低于阈值 ({current_credits} < {credits_threshold})",
        current_credits=current_credits
    )


async def _ensure_admin_token(db: Session, team: TeamConfig, force_refresh: bool = False) -> str:
    """确保管理员Token有效，必要时刷新或重新登录"""
    from app.windsurf_api import login_with_email
    import base64
    import json
    
    # 检测 token 是否过期（手动解析 JWT，无需 PyJWT 库）
    def is_token_expired(token: str) -> bool:
        if not token:
            return True
        try:
            # JWT 格式: header.payload.signature
            parts = token.split('.')
            if len(parts) != 3:
                return True
            # 解码 payload（第二部分）
            payload = parts[1]
            # 补齐 base64 padding
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)
            exp = data.get("exp", 0)
            # 提前5分钟认为过期，留出缓冲时间
            return datetime.utcnow().timestamp() > (exp - 300)
        except Exception as e:
            print(f"⚠️ [TeamAuth] Token解析失败，将重新登录: {e}")
            return True
    
    # 如果有token且未过期且不强制刷新，直接使用
    if team.admin_token and not force_refresh and not is_token_expired(team.admin_token):
        return team.admin_token
    
    # Token过期或不存在，重新登录获取
    if team.admin_email and team.admin_password:
        print(f"🔄 [TeamAuth] 管理员Token过期或不存在，重新登录: {team.admin_email}")
        login_result = await login_with_email(team.admin_email, team.admin_password, db)
        if login_result.get("success"):
            team.admin_token = login_result.get("id_token")
            team.admin_api_key = login_result.get("local_id")
            db.commit()
            print(f"✅ [TeamAuth] 管理员登录成功: {team.admin_email}")
            return team.admin_token
        else:
            print(f"❌ [TeamAuth] 管理员登录失败: {login_result.get('error')}")
    
    return None


async def _check_and_switch_member(db: Session, team: TeamConfig) -> dict:
    """
    检测当前成员积分并在需要时自动切换
    在一键换号时触发，不需要定时检测
    
    Returns:
        dict: 切换信息，如果没有切换则返回None
    """
    from app.windsurf_api import get_current_user, get_member_used_credits, login_with_email, update_codeium_access
    
    # 获取当前成员
    current_member = db.query(TeamMember).filter(
        TeamMember.team_id == team.id,
        TeamMember.is_current == True
    ).first()
    
    if not current_member:
        print(f"⚠️ [CreditsCheck] 团队 {team.name} 没有当前成员")
        return None
    
    # 获取当前成员的实时积分
    credits = current_member.last_credits
    credits_from_api = False
    
    # 方案1: 使用管理员 token 获取成员的个人已用积分（更准确）
    admin_token = await _ensure_admin_token(db, team)
    if admin_token:
        try:
            print(f"🔄 [CreditsCheck] 使用管理员Token获取成员已用积分: {current_member.email}")
            member_used = await get_member_used_credits(admin_token, current_member.email)
            if member_used is not None:
                # 获取月度配额（从 GetCurrentUser 获取）
                if current_member.password:
                    login_result = await login_with_email(current_member.email, current_member.password, db)
                    if login_result.get("success"):
                        member_token = login_result.get("id_token")
                        user_result = await get_current_user(member_token)
                        if user_result.get("success"):
                            total_quota = user_result.get("total_quota", 500)
                            credits = max(0, total_quota - member_used)
                            credits_from_api = True
                            print(f"📊 [CreditsCheck] {current_member.email}: 总配额={total_quota}, 已用={member_used}, 剩余={credits}")
        except Exception as e:
            print(f"⚠️ [CreditsCheck] 通过管理员获取积分失败: {e}")
    
    # 方案2: 如果管理员方式失败，使用成员自己的 token 获取（回退方案）
    if not credits_from_api and current_member.password:
        try:
            print(f"🔄 [CreditsCheck] 回退：使用成员账号获取积分: {current_member.email}")
            login_result = await login_with_email(current_member.email, current_member.password, db)
            if login_result.get("success"):
                member_token = login_result.get("id_token")
                user_result = await get_current_user(member_token)
                if user_result.get("success"):
                    remaining = user_result.get("remaining_credits")
                    if remaining is not None:
                        credits = remaining
                        credits_from_api = True
                        print(f"📊 [CreditsCheck] {current_member.email}: 剩余积分={remaining} (回退方案)")
        except Exception as e:
            print(f"⚠️ [CreditsCheck] 获取积分失败: {e}")
    
    # 更新数据库中的积分记录
    if credits_from_api:
        current_member.last_credits = credits
    current_member.last_check_at = datetime.utcnow()
    team.last_check_at = datetime.utcnow()
    
    # 判断是否需要切换
    if credits >= team.credits_threshold:
        db.commit()
        print(f"✅ [CreditsCheck] 积分充足 ({credits} >= {team.credits_threshold})，无需切换")
        return None
    
    print(f"⚠️ [CreditsCheck] 积分不足 ({credits} < {team.credits_threshold})，需要切换成员")
    
    # 查找下一个可用成员（跳过已用尽的成员）
    members = db.query(TeamMember).filter(
        TeamMember.team_id == team.id,
        TeamMember.id != current_member.id,
        TeamMember.is_exhausted == False  # 跳过已用尽的成员
    ).order_by(TeamMember.sort_order).all()
    
    next_member = None
    for m in members:
        if not m.is_enabled:
            next_member = m
            break
    
    if not next_member:
        db.commit()
        print(f"⚠️ [CreditsCheck] 没有可用的成员可切换")
        return {"switched": False, "message": "没有可用的成员可切换", "credits": credits}
    
    # 获取管理员Token用于调用Windsurf API
    admin_token = await _ensure_admin_token(db, team)
    
    # 执行切换 - 调用Windsurf API禁用/启用成员
    if admin_token:
        print(f"🔑 [CreditsCheck] 管理员Token已获取，开始调用Windsurf API")
        
        # 禁用当前成员
        if current_member.api_key:
            print(f"🔄 [CreditsCheck] 禁用成员: {current_member.email}, api_key={current_member.api_key[:20]}...")
            disable_result = await update_codeium_access(admin_token, current_member.api_key, True)
            if disable_result.get("success"):
                print(f"✅ [CreditsCheck] 已禁用成员: {current_member.email}")
            else:
                print(f"⚠️ [CreditsCheck] 禁用成员失败: {disable_result}")
        else:
            print(f"⚠️ [CreditsCheck] 当前成员 {current_member.email} 没有api_key，无法调用禁用API")
        
        # 启用新成员
        if next_member.api_key:
            print(f"🔄 [CreditsCheck] 启用成员: {next_member.email}, api_key={next_member.api_key[:20]}...")
            enable_result = await update_codeium_access(admin_token, next_member.api_key, False)
            if enable_result.get("success"):
                print(f"✅ [CreditsCheck] 已启用成员: {next_member.email}")
            else:
                print(f"⚠️ [CreditsCheck] 启用成员失败: {enable_result}")
        else:
            print(f"⚠️ [CreditsCheck] 新成员 {next_member.email} 没有api_key，无法调用启用API")
    else:
        print(f"⚠️ [CreditsCheck] 无法获取管理员Token，跳过Windsurf API调用")
    
    # 更新数据库状态
    current_member.is_current = False
    current_member.is_enabled = False
    current_member.is_exhausted = True  # 标记为已用尽，不再切换回来
    current_member.disabled_at = datetime.utcnow()
    
    next_member.is_current = True
    next_member.is_enabled = True
    next_member.enabled_at = datetime.utcnow()
    
    team.current_member_id = next_member.id
    team.last_switch_at = datetime.utcnow()
    team.switch_count += 1
    
    # 记录切换历史
    history = MemberSwitchHistory(
        team_id=team.id,
        from_member_id=current_member.id,
        to_member_id=next_member.id,
        from_email=current_member.email,
        to_email=next_member.email,
        reason=f"一键换号时积分不足 ({credits} < {team.credits_threshold})",
        credits_before=credits
    )
    db.add(history)
    
    # 更新固定Pro账号配置
    _update_fixed_pro_config(db, next_member.email, next_member.password)
    
    db.commit()
    
    print(f"🔄 [CreditsCheck] 成员切换完成: {current_member.email} -> {next_member.email}")
    
    return {
        "switched": True,
        "from_member": current_member.email,
        "to_member": next_member.email,
        "credits": credits,
        "message": f"积分不足已自动切换: {current_member.email} -> {next_member.email}"
    }


def _update_fixed_pro_config(db: Session, email: str, password: str):
    """更新固定Pro账号配置"""
    # 更新邮箱
    email_config = db.query(Config).filter(Config.key == "fixed_pro_email").first()
    if email_config:
        email_config.value = email
    else:
        db.add(Config(key="fixed_pro_email", value=email))
    
    # 更新密码
    password_config = db.query(Config).filter(Config.key == "fixed_pro_password").first()
    if password_config:
        password_config.value = password
    else:
        db.add(Config(key="fixed_pro_password", value=password))


@router.post("/team/{team_id}/check-credits", response_model=TeamCreditsCheckResponse)
async def check_member_credits(
    team_id: int,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    检测当前成员的积分
    调用Windsurf GetPlanStatus API获取实时积分
    """
    from app.windsurf_api import get_plan_status, login_with_email
    
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    current_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.is_current == True
    ).first()
    
    if not current_member:
        return TeamCreditsCheckResponse(
            success=False,
            message="没有当前成员"
        )
    
    # 尝试获取成员的实时积分
    credits = current_member.last_credits
    credits_remaining = None
    
    # 如果成员有密码，尝试登录获取积分
    if current_member.password:
        login_result = await login_with_email(current_member.email, current_member.password, db)
        if login_result.get("success"):
            member_token = login_result.get("id_token")
            # 获取积分状态
            plan_result = await get_plan_status(member_token)
            if plan_result.get("success"):
                prompts_used = plan_result.get("prompts_used")
                if prompts_used is not None:
                    # Windsurf返回的是已用积分，需要计算剩余
                    # 假设每月500积分上限
                    credits_limit = plan_result.get("prompts_limit") or 500
                    credits = credits_limit - prompts_used
                    credits_remaining = credits
                    print(f"📊 [CreditsCheck] {current_member.email}: used={prompts_used}, remaining={credits}")
    
    # 更新数据库
    current_member.last_credits = credits
    current_member.last_check_at = datetime.utcnow()
    team.last_check_at = datetime.utcnow()
    db.commit()
    
    need_switch = credits < team.credits_threshold
    
    return TeamCreditsCheckResponse(
        success=True,
        message="积分检测完成",
        email=current_member.email,
        credits=credits,
        credits_remaining=credits_remaining,
        need_switch=need_switch
    )


@router.put("/team/{team_id}/members/{member_id}/credits")
async def update_member_credits(
    team_id: int,
    member_id: int,
    credits: int,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """更新成员积分（由客户端调用Windsurf API后更新）"""
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.team_id == team_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 验证团队归属
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key or key.team_id != team_id:
        raise HTTPException(status_code=404, detail="团队不存在或无权限")
    
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    member.last_credits = credits
    member.last_check_at = datetime.utcnow()
    db.commit()
    
    return {
        "success": True,
        "message": "积分已更新",
        "credits": credits,
        "need_switch": credits < team.credits_threshold
    }
