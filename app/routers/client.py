from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
import math
import os

from app.database import get_db
from app.models import Account, Key, AccountStatus, KeyStatus, KeyType, Config
from app.schemas import AccountGetResponse, KeyStatusResponse, VersionResponse
from app.auth import get_api_key
from app.utils import calculate_remaining_time

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
    
    else:  # limited 有限额度
        # 有限额度：只检查总额度限制
        if (key.account_limit or 0) > 0:
            remaining = max(key.account_limit - key.request_count, 0)
            if remaining <= 0:
                raise HTTPException(status_code=403, detail="密钥额度已用尽")
    
    # === 获取账号 ===
    
    # 自动将创建时间超过指定天数的未使用账号设置为过期
    expiry_threshold = now - timedelta(days=ACCOUNT_EXPIRY_DAYS)
    expired_accounts = db.query(Account).filter(
        Account.status == AccountStatus.unused,
        Account.created_at < expiry_threshold
    ).update({Account.status: AccountStatus.expired}, synchronize_session=False)
    
    if expired_accounts > 0:
        db.commit()
    
    # 获取未使用的账号，优先获取创建时间最久的
    account = db.query(Account).filter(
        Account.status == AccountStatus.unused
    ).order_by(Account.created_at.asc()).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="暂无可用账号")
    
    # 更新账号状态
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
    
    # 根据密钥类型决定是否返回密码
    response_data = {
        "email": account.email,
        "api_key": account.api_key
    }
    
    if key.key_type == KeyType.limited:
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
        remaining_accounts=remaining_accounts
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
