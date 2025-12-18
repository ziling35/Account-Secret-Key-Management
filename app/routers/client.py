from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
import math
import os

from app.database import get_db
from app.models import Account, Key, AccountStatus, KeyStatus, KeyType, Config, Announcement, VersionNote, PluginInfo
from app.schemas import AccountGetResponse, KeyStatusResponse, VersionResponse, AnnouncementResponse, LoginRequest, LoginResponse, AccountHistoryResponse, AccountHistoryItem, VersionNotesResponse, VersionNoteItem, PluginInfoResponse, PluginVersionCheckResponse, PluginListResponse, PluginListItem
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
    db: Session = Depends(get_db)
):
    """
    客户端获取未使用账号
    - 需要在请求头中提供 X-API-Key
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
    
    # 检查密钥状态（使用 UTC 时间）
    now = datetime.utcnow()
    today = date.today()
    
    # 如果是首次使用，激活密钥
    if key.status == KeyStatus.inactive:
        key.status = KeyStatus.active
        key.activated_at = now
        key.expires_at = now + timedelta(days=key.duration_days)
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
    
    # Pro类型卡密特殊处理：允许获取相同账号，不排除之前获取过的
    if key.key_type == KeyType.pro:
        # Pro卡密：随机获取一个Pro账号（可以重复获取）
        from sqlalchemy.sql.expression import func
        query = db.query(Account).filter(
            Account.is_pro == True,
            Account.status != AccountStatus.expired  # 排除过期账号
        )
        account = query.order_by(func.random()).first()  # 随机选取
        
        if not account:
            raise HTTPException(status_code=404, detail="暂无可用的Pro账号")
    else:
        # 非Pro卡密：查询该密钥之前获取过的账号邮箱列表
        previously_assigned_emails = db.query(Account.email).filter(
            Account.assigned_to_key == api_key
        ).all()
        previously_assigned_emails = [email[0] for email in previously_assigned_emails]
        
        # 获取未使用的账号，排除该密钥之前获取过的账号，优先获取创建时间最久的
        query = db.query(Account).filter(
            Account.status == AccountStatus.unused
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
            # 通过登录获取 API Key
            login_result = await windsurf_login(
                email=account.email,
                password=account.password,
                db=db
            )
            
            # 更新账号的 API Key
            account.api_key = login_result['api_key']
            # 如果名字为空，也更新名字
            if not account.name or account.name.strip() == '':
                account.name = login_result['name']
            
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
                    # Pro卡密：随机获取另一个Pro账号
                    from sqlalchemy.sql.expression import func
                    query = db.query(Account).filter(
                        Account.is_pro == True,
                        Account.status != AccountStatus.expired,
                        Account.id != account.id  # 排除当前失败的账号
                    )
                    account = query.order_by(func.random()).first()
                else:
                    query = db.query(Account).filter(
                        Account.status == AccountStatus.unused
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
    
    # Pro卡密不更新账号状态（允许重复使用）
    if key.key_type != KeyType.pro:
        account.status = AccountStatus.used
        account.assigned_at = now
        account.assigned_to_key = api_key
    
    # 更新密钥统计
    key.request_count += 1
    key.last_request_at = now
    key.last_request_ip = request.client.host
    
    # 无限额度：增加每日计数
    if key.key_type == KeyType.unlimited:
        key.daily_request_count += 1
    
    db.commit()
    
    # 根据密钥类型决定返回内容
    response_data = {
        "email": account.email,
        "api_key": account.api_key,
        "is_pro": account.is_pro
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
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    查询密钥状态和剩余时间
    - 需要在请求头中提供 X-API-Key
    - 首次查询时自动激活密钥
    """
    # 验证密钥
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    now = datetime.utcnow()
    
    # 如果是首次使用，激活密钥
    if key.status == KeyStatus.inactive:
        key.status = KeyStatus.active
        key.activated_at = now
        key.expires_at = now + timedelta(days=key.duration_days)
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
    """
    # 验证密钥
    key = db.query(Key).filter(Key.key_code == api_key).first()
    if not key:
        raise HTTPException(status_code=401, detail="无效的API密钥")
    
    # 检查是否被禁用
    if key.is_disabled:
        raise HTTPException(status_code=403, detail="密钥已被管理员禁用")
    
    try:
        # 查询该密钥关联的所有账号
        accounts = db.query(Account).filter(
            Account.assigned_to_key == api_key
        ).order_by(Account.assigned_at.desc()).all()
        
        # 转换为响应格式
        account_list = [
            AccountHistoryItem(
                email=acc.email,
                password=acc.password,
                api_key=acc.api_key,
                name=acc.name,
                assigned_at=acc.assigned_at
            )
            for acc in accounts
        ]
        
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
