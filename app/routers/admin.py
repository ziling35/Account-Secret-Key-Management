from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, case, func
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Account, ProAccount, Key, AccountStatus, KeyStatus, KeyType, Config, Announcement, VersionNote, PluginInfo, DeviceBinding
from app.schemas import (
    AccountResponse, KeyCreate, KeyResponse, StatsResponse,
    AnnouncementCreate, AnnouncementUpdate, AnnouncementListItem,
    VersionNoteCreate, VersionNoteUpdate, VersionNoteItem,
    PluginInfoCreate, PluginInfoUpdate, PluginInfoListItem
)
from app.auth import verify_admin, create_session, check_credentials
from app.utils import (
    generate_key_code, parse_account_file, 
    calculate_remaining_time, format_datetime
)
import os

INTERNAL_UPLOAD_TOKEN = os.getenv("INTERNAL_UPLOAD_TOKEN", "CHANGE_ME_INTERNAL_TOKEN")

router = APIRouter(prefix="/admin", tags=["管理端"])
templates = Jinja2Templates(directory="app/templates")

# ==================== 登录/登出 ====================

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """登录处理"""
    if not check_credentials(username, password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 创建Session
    session_token = create_session(username)
    
    response = JSONResponse(content={"success": True})
    response.set_cookie(
        key="admin_session",
        value=session_token,
        httponly=True,
        max_age=86400,  # 24小时
        samesite="lax"
    )
    return response

@router.get("/logout")
async def logout():
    """登出"""
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_session")
    return response

# ==================== 页面路由 ====================

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request, username: str = Depends(verify_admin), db: Session = Depends(get_db)):
    """管理仪表盘"""
    stats = get_statistics(db)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats
    })

@router.get("/keys", response_class=HTMLResponse)
async def keys_page(request: Request, username: str = Depends(verify_admin)):
    """密钥管理页面"""
    return templates.TemplateResponse("keys.html", {"request": request})

@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, username: str = Depends(verify_admin)):
    """账号管理页面"""
    return templates.TemplateResponse("accounts.html", {"request": request})

@router.get("/announcements", response_class=HTMLResponse)
async def announcements_page(request: Request, username: str = Depends(verify_admin)):
    """公告管理页面"""
    return templates.TemplateResponse("announcements.html", {"request": request})

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, username: str = Depends(verify_admin)):
    """系统设置页面"""
    return templates.TemplateResponse("settings.html", {"request": request})

# ==================== API接口 ====================

@router.get("/api/stats", response_model=StatsResponse)
async def get_stats(username: str = Depends(verify_admin), db: Session = Depends(get_db)):
    """获取统计信息"""
    return get_statistics(db)

@router.post("/api/keys/create")
async def create_keys(
    count: int,
    key_type: str,
    duration_days: int = 0,
    duration_hours: int = 0,
    notes: str = "",
    account_limit: int = 0,
    team_card_key: str = "",
    team_id: int = None,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """批量创建密钥"""
    if count <= 0 or count > 100:
        raise HTTPException(status_code=400, detail="数量必须在1-100之间")
    
    if key_type not in ["unlimited", "limited", "pro", "team"]:
        raise HTTPException(status_code=400, detail="密钥类型必须为 unlimited、limited、pro 或 team")
    
    # 验证有效期：天数和小时数至少有一个大于0
    if duration_days <= 0 and duration_hours <= 0:
        raise HTTPException(status_code=400, detail="有效期必须大于0（天数或小时数至少填一个）")
    
    if account_limit < -1:
        raise HTTPException(status_code=400, detail="账号配额无效（-1=不限制, 0=仅授权不含账号, >0=固定配额）")
    
    # 验证无限额度类型
    if key_type == "unlimited" and account_limit > 0:
        raise HTTPException(status_code=400, detail="无限额度类型的账号配额必须为0")
    
    # 验证Team类型：必须提供第三方卡密（允许批量创建，共用同一个第三方卡密）
    if key_type == "team":
        if not team_card_key or not team_card_key.strip():
            raise HTTPException(status_code=400, detail="Team类型必须提供第三方卡密")
    
    # 验证有限额度类型：允许 account_limit = 0，表示不能获取账号但密钥可用于插件授权
    
    keys = []
    for _ in range(count):
        key_code = generate_key_code()
        # 确保密钥唯一
        while db.query(Key).filter(Key.key_code == key_code).first():
            key_code = generate_key_code()
        
        key = Key(
            key_code=key_code,
            key_type=KeyType[key_type],
            duration_days=duration_days,
            duration_hours=duration_hours,
            notes=notes,
            account_limit=account_limit,
            team_card_key=team_card_key.strip() if key_type == "team" else None,
            team_id=team_id if key_type == "pro" else None
        )
        db.add(key)
        keys.append(key_code)
    
    db.commit()
    
    return {
        "success": True,
        "count": len(keys),
        "keys": keys,
        "preview": "\n".join(keys)
    }

@router.get("/api/keys/export")
async def export_keys(
    status: str = None,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """导出密钥列表为txt文件"""
    query = db.query(Key)
    
    # 根据状态筛选
    if status:
        query = query.filter(Key.status == KeyStatus[status])
    
    keys = query.order_by(Key.created_at.desc()).all()
    
    if not keys:
        raise HTTPException(status_code=404, detail="没有密钥可导出")
    
    # 生成导出内容
    lines = []
    lines.append("=" * 80)
    lines.append(f"密钥列表导出")
    lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"总数量: {len(keys)}")
    if status:
        lines.append(f"筛选状态: {status}")
    lines.append("=" * 80)
    lines.append("")
    
    for idx, key in enumerate(keys, 1):
        lines.append(f"密钥 {idx}:")
        lines.append(f"  代码: {key.key_code}")
        lines.append(f"  状态: {key.status.value}")
        duration_hours = getattr(key, 'duration_hours', 0) or 0
        duration_str = f"{key.duration_days}天" + (f" {duration_hours}小时" if duration_hours else "")
        lines.append(f"  有效期: {duration_str}")
        lines.append(f"  创建时间: {key.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if key.activated_at:
            lines.append(f"  激活时间: {key.activated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if key.expires_at:
            lines.append(f"  过期时间: {key.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  请求次数: {key.request_count}")
        # 配额信息
        limit = key.account_limit or 0
        remaining = (max(limit - (key.request_count or 0), 0) if limit > 0 else -1)
        lines.append(f"  账号配额: {'不限' if limit <= 0 else limit}")
        lines.append(f"  剩余额度: {'不限' if remaining == -1 else remaining}")
        if key.notes:
            lines.append(f"  备注: {key.notes}")
        lines.append("")
    
    content = "\n".join(lines)
    filename = f"keys_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    return Response(
        content=content.encode('utf-8'),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@router.get("/api/keys/list")
async def list_keys(
    page: int = 1,
    page_size: int = 10,
    status: str = None,
    sort: str = None,
    search: str = None,
    activated_from: str = None,
    activated_to: str = None,
    key_type: str = None,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取密钥列表（分页，最多10/页）"""
    # 规范参数
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10
    if page_size > 10:
        page_size = 10
    query = db.query(Key)
    
    if status:
        try:
            query = query.filter(Key.status == KeyStatus[status])
        except Exception:
            pass
    # 关键字搜索（密钥代码）
    if search:
        s = search.strip().lower()
        if s:
            query = query.filter(func.lower(Key.key_code).like(f"%{s}%"))
    
    # 类型过滤（limited/unlimited）
    if key_type:
        try:
            query = query.filter(Key.key_type == KeyType[key_type])
        except Exception:
            pass
    
    # 激活时间范围过滤（日期字符串 YYYY-MM-DD）
    from_dt = None
    to_dt_next = None
    if activated_from:
        try:
            from_dt = datetime.strptime(activated_from, "%Y-%m-%d")
        except Exception:
            from_dt = None
    if activated_to:
        try:
            to_dt = datetime.strptime(activated_to, "%Y-%m-%d")
            to_dt_next = to_dt + timedelta(days=1)
        except Exception:
            to_dt_next = None
    if from_dt is not None:
        query = query.filter(Key.activated_at.isnot(None), Key.activated_at >= from_dt)
    if to_dt_next is not None:
        query = query.filter(Key.activated_at.isnot(None), Key.activated_at < to_dt_next)
    
    # 计算总数
    total = query.count()
    
    # 分页查询与排序
    skip = (page - 1) * page_size

    order_by_clauses = []
    if sort:
        parts = [p.strip() for p in sort.split(',') if p.strip()]
        for part in parts:
            if ':' in part:
                field, direction = part.split(':', 1)
            else:
                field, direction = part, 'desc'
            direction = direction.lower()
            is_desc = direction != 'asc'
            col = None
            if field == 'duration_days':
                col = Key.duration_days
            elif field == 'activated_at':
                col = Key.activated_at
            elif field in ('remaining_time', 'expires_at'):
                col = Key.expires_at
            elif field == 'account_limit':
                # 无上限(0)在排序时作为最大值处理
                col = case((Key.account_limit == 0, 10**9), else_=Key.account_limit)
            elif field == 'remaining_accounts':
                # 有限额度：按剩余量排序；无限额度：作为最大值处理
                col = case((Key.account_limit > 0, (Key.account_limit - Key.request_count)), else_=10**9)
            elif field == 'request_count':
                col = Key.request_count
            elif field == 'created_at':
                col = Key.created_at
            elif field == 'key_type':
                # unlimited 优先或置前（0）/ limited 置后（1）
                col = case((Key.key_type == KeyType.unlimited, 0), else_=1)
            if col is not None:
                order_by_clauses.append(desc(col) if is_desc else asc(col))
    if not order_by_clauses:
        order_by_clauses = [desc(Key.created_at)]

    keys = query.order_by(*order_by_clauses).offset(skip).limit(page_size).all()
    
    # 添加剩余时间计算
    result = []
    for key in keys:
        key_dict = KeyResponse.from_orm(key).model_dump()
        # Enum 转字符串，确保前端拿到的是字符串
        try:
            key_dict['key_type'] = key.key_type.value if key.key_type else 'limited'
        except Exception:
            key_dict['key_type'] = 'limited'
        if key.expires_at:
            key_dict['remaining_time'] = calculate_remaining_time(key.expires_at)
        else:
            key_dict['remaining_time'] = "未激活"
        # 额度信息
        limit = key.account_limit or 0
        key_dict['account_limit'] = limit
        key_dict['remaining_accounts'] = (max(limit - (key.request_count or 0), 0) if limit > 0 else -1)
        
        # 添加设备绑定信息
        device_bindings = db.query(DeviceBinding).filter(
            DeviceBinding.key_code == key.key_code,
            DeviceBinding.is_active == True
        ).all()
        key_dict['device_count'] = len(device_bindings)
        key_dict['max_devices'] = key.max_devices if hasattr(key, 'max_devices') else 3
        
        result.append(key_dict)
    
    return {
        "keys": result,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.get("/api/accounts/list")
async def list_accounts(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    is_pro: str = None,
    sort: str = None,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取账号列表（分页）
    - is_pro: 筛选Pro账号 ('true' 或 'false')
    - Pro账号从 ProAccount 表查询，普通账号从 Account 表查询
    """
    # 判断是否查询 Pro 账号
    query_pro = is_pro is not None and is_pro.lower() == 'true'
    
    if query_pro:
        # 查询 ProAccount 表
        query = db.query(ProAccount)
        if status:
            try:
                query = query.filter(ProAccount.status == AccountStatus[status])
            except Exception:
                pass
        
        total = query.count()
        skip = (page - 1) * page_size
        
        order_by_clauses = []
        if sort:
            parts = [p.strip() for p in sort.split(',') if p.strip()]
            for part in parts:
                if ':' in part:
                    field, direction = part.split(':', 1)
                else:
                    field, direction = part, 'desc'
                direction = direction.lower()
                is_desc = direction != 'asc'
                col = None
                if field == 'assigned_at':
                    col = ProAccount.assigned_at
                elif field == 'created_at':
                    col = ProAccount.created_at
                if col is not None:
                    order_by_clauses.append(desc(col) if is_desc else asc(col))
        if not order_by_clauses:
            order_by_clauses = [desc(ProAccount.created_at)]
        
        accounts = query.order_by(*order_by_clauses).offset(skip).limit(page_size).all()
        
        # 转换为响应格式（ProAccount 没有 is_pro 字段，手动添加）
        accounts_data = []
        for acc in accounts:
            accounts_data.append({
                "id": acc.id,
                "email": acc.email,
                "password": acc.password,
                "api_key": acc.api_key,
                "name": acc.name,
                "status": acc.status.value,
                "is_pro": True,
                "created_at": acc.created_at,
                "assigned_at": acc.assigned_at,
                "assigned_to_key": acc.assigned_to_key
            })
    else:
        # 查询 Account 表（普通账号）
        query = db.query(Account)
        if status:
            try:
                query = query.filter(Account.status == AccountStatus[status])
            except Exception:
                pass
        
        # 排除 Pro 账号（如果 is_pro='false'）或显示全部普通账号
        if is_pro is not None and is_pro.lower() == 'false':
            query = query.filter(Account.is_pro == False)
        
        total = query.count()
        skip = (page - 1) * page_size

        order_by_clauses = []
        if sort:
            parts = [p.strip() for p in sort.split(',') if p.strip()]
            for part in parts:
                if ':' in part:
                    field, direction = part.split(':', 1)
                else:
                    field, direction = part, 'desc'
                direction = direction.lower()
                is_desc = direction != 'asc'
                col = None
                if field == 'assigned_at':
                    col = Account.assigned_at
                elif field == 'created_at':
                    col = Account.created_at
                if col is not None:
                    order_by_clauses.append(desc(col) if is_desc else asc(col))
        if not order_by_clauses:
            order_by_clauses = [desc(Account.created_at)]

        accounts = query.order_by(*order_by_clauses).offset(skip).limit(page_size).all()
        accounts_data = [AccountResponse.from_orm(account).model_dump() for account in accounts]
    
    return {
        "accounts": accounts_data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.post("/api/keys/toggle-disable/{key_id}")
async def toggle_key_disable(
    key_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """禁用或恢复密钥"""
    key = db.query(Key).filter(Key.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="密钥不存在")
    
    # 切换禁用状态
    key.is_disabled = not key.is_disabled
    db.commit()
    
    status_text = "已禁用" if key.is_disabled else "已恢复"
    return {
        "success": True,
        "message": f"密钥{status_text}",
        "is_disabled": key.is_disabled
    }

@router.delete("/api/keys/delete/{key_id}")
async def delete_key(
    key_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """删除密钥"""
    key = db.query(Key).filter(Key.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="密钥不存在")
    
    # 保存密钥信息用于日志
    key_code = key.key_code
    key_status = key.status.value
    
    # 删除密钥
    db.delete(key)
    db.commit()
    
    return {
        "success": True,
        "message": f"密钥 {key_code[:8]}... 已删除",
        "key_id": key_id,
        "key_code": key_code,
        "old_status": key_status
    }

@router.post("/api/accounts/update-status/{account_id}")
async def update_account_status(
    account_id: int,
    status: str,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """手动修改账号状态"""
    # 验证状态值
    if status not in ["unused", "used", "expired"]:
        raise HTTPException(status_code=400, detail="无效的状态值，必须是 unused、used 或 expired")
    
    # 查找账号
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    old_status = account.status.value
    
    # 更新状态
    account.status = AccountStatus[status]
    
    # 如果设置为已使用状态，更新分配时间
    if status == "used" and not account.assigned_at:
        account.assigned_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"账号状态已从 {old_status} 更新为 {status}",
        "account_id": account_id,
        "old_status": old_status,
        "new_status": status
    }

@router.post("/api/accounts/toggle-pro/{account_id}")
async def toggle_account_pro(
    account_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """切换账号的Pro状态（已废弃）
    注意：Pro账号现在使用单独的 ProAccount 表，此接口仅对旧的 Account 表中的 is_pro 字段有效
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在（注意：Pro账号现在在单独的表中）")
    
    old_is_pro = account.is_pro
    account.is_pro = not account.is_pro
    db.commit()
    
    status_text = "Pro账号" if account.is_pro else "普通账号"
    return {
        "success": True,
        "message": f"账号已设为{status_text}（注意：新Pro账号请直接上传到ProAccount表）",
        "account_id": account_id,
        "is_pro": account.is_pro,
        "old_is_pro": old_is_pro
    }

@router.delete("/api/accounts/{account_id}")
async def delete_account(
    account_id: int,
    is_pro: str = "false",
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """删除单个账号
    - is_pro: 'true' 删除 ProAccount 表中的账号，'false' 删除 Account 表中的账号
    """
    is_pro_bool = is_pro.lower() == 'true'
    
    if is_pro_bool:
        account = db.query(ProAccount).filter(ProAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Pro账号不存在")
        email = account.email
        db.delete(account)
        db.commit()
        return {
            "success": True,
            "message": f"Pro账号 {email} 已删除",
            "account_id": account_id,
            "is_pro": True
        }
    else:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        email = account.email
        db.delete(account)
        db.commit()
        return {
            "success": True,
            "message": f"账号 {email} 已删除",
            "account_id": account_id,
            "is_pro": False
        }

@router.post("/api/accounts/batch-delete")
async def batch_delete_accounts(
    account_ids: List[int],
    is_pro: str = "false",
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """批量删除账号
    - is_pro: 'true' 删除 ProAccount 表中的账号，'false' 删除 Account 表中的账号
    """
    if not account_ids:
        raise HTTPException(status_code=400, detail="未提供账号ID列表")
    
    is_pro_bool = is_pro.lower() == 'true'
    
    if is_pro_bool:
        deleted_count = db.query(ProAccount).filter(ProAccount.id.in_(account_ids)).delete(synchronize_session=False)
    else:
        deleted_count = db.query(Account).filter(Account.id.in_(account_ids)).delete(synchronize_session=False)
    db.commit()
    
    account_type = "Pro账号" if is_pro_bool else "账号"
    return {
        "success": True,
        "message": f"已删除 {deleted_count} 个{account_type}",
        "deleted_count": deleted_count,
        "is_pro": is_pro_bool
    }

@router.get("/api/accounts/credits/{account_id}")
async def get_account_credits(
    account_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """查询账号积分信息"""
    from app.windsurf_login import get_account_credits as query_credits
    
    # 查找账号
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    try:
        # 调用积分查询服务
        credits_info = await query_credits(
            email=account.email,
            password=account.password,
            db=db
        )
        
        return {
            "success": True,
            "account_id": account_id,
            "email": account.email,
            "credits": {
                "name": credits_info.get('name', ''),
                "is_pro": credits_info.get('is_pro', False),
                "plan_type": credits_info.get('plan_type', 'unknown'),
                "user_used_prompt_credits": credits_info.get('user_used_prompt_credits', 0),
                "user_used_flow_credits": credits_info.get('user_used_flow_credits', 0),
                "team_name": credits_info.get('team_name', ''),
                "team_flex_credit_quota": credits_info.get('team_flex_credit_quota', 0),
                "team_used_flex_credits": credits_info.get('team_used_flex_credits', 0),
                "team_used_prompt_credits": credits_info.get('team_used_prompt_credits', 0),
                "team_used_flow_credits": credits_info.get('team_used_flow_credits', 0),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询积分失败: {str(e)}")


@router.post("/api/accounts/upload")
async def upload_accounts(
    files: List[UploadFile] = File(...),
    is_pro: str = Form("false"),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """上传账号批量文件（支持多文件）
    - is_pro: 是否为Pro账号
    """
    # 手动解析字符串布尔值
    is_pro_bool = is_pro.lower() in ('true', '1', 'yes')
    
    total_accounts = 0
    success_count = 0
    duplicate_count = 0
    seen_emails = set()  # 跟踪本次上传中已处理的邮箱
    
    for file in files:
        if not file.filename.endswith('.txt'):
            continue  # 跳过非txt文件
        
        # 读取文件内容
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # 解析账号
        accounts_data = parse_account_file(content_str)
        
        if not accounts_data:
            continue
        
        total_accounts += len(accounts_data)
        
        # 批量插入
        for acc_data in accounts_data:
            email = acc_data['email'].lower()  # 统一小写比较
            
            if is_pro_bool:
                # Pro账号：使用单独的 ProAccount 表，允许重复邮箱（不检查去重）
                pro_account = ProAccount(
                    email=acc_data['email'],
                    name=acc_data['name'],
                    password=acc_data['password'],
                    api_key=acc_data['api_key']
                )
                db.add(pro_account)
                success_count += 1
                continue
            
            # 普通账号：检查本次上传中是否已有相同邮箱（批量内去重，避免数据库唯一约束冲突）
            if email in seen_emails:
                duplicate_count += 1
                continue
            
            # 普通账号：检查数据库中是否已存在
            existing = db.query(Account).filter(Account.email == acc_data['email']).first()
            if existing:
                duplicate_count += 1
                seen_emails.add(email)
                continue
            
            account = Account(
                email=acc_data['email'],
                name=acc_data['name'],
                password=acc_data['password'],
                api_key=acc_data['api_key'],
                is_pro=False
            )
            db.add(account)
            seen_emails.add(email)
            success_count += 1
    
    db.commit()
    
    if total_accounts == 0:
        raise HTTPException(status_code=400, detail="未解析到有效账号")
    
    return {
        "success": True,
        "total": total_accounts,
        "success_count": success_count,
        "duplicate_count": duplicate_count,
        "is_pro": is_pro_bool
    }


@router.post("/internal/api/accounts/upload")
async def internal_upload_accounts(
    request: Request,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    token = request.headers.get("X-Internal-Token")
    if not token or token != INTERNAL_UPLOAD_TOKEN:
        raise HTTPException(status_code=401, detail="invalid internal token")

    total_accounts = 0
    success_count = 0
    duplicate_count = 0
    seen_emails = set()  # 跟踪本次上传中已处理的邮箱
    
    for file in files:
        if not file.filename.endswith('.txt'):
            continue
        
        content = await file.read()
        content_str = content.decode('utf-8')
        
        accounts_data = parse_account_file(content_str)
        
        if not accounts_data:
            continue
        
        total_accounts += len(accounts_data)
        
        for acc_data in accounts_data:
            email = acc_data['email'].lower()  # 统一小写比较
            
            # 检查本次上传中是否已有相同邮箱
            if email in seen_emails:
                duplicate_count += 1
                continue
            
            # 检查数据库中是否已存在
            existing = db.query(Account).filter(Account.email == acc_data['email']).first()
            if existing:
                duplicate_count += 1
                seen_emails.add(email)
                continue
            
            account = Account(
                email=acc_data['email'],
                name=acc_data['name'],
                password=acc_data['password'],
                api_key=acc_data['api_key']
            )
            db.add(account)
            seen_emails.add(email)
            success_count += 1
    
    db.commit()
    
    if total_accounts == 0:
        raise HTTPException(status_code=400, detail="未解析到有效账号")
    
    return {
        "success": True,
        "total": total_accounts,
        "success_count": success_count,
        "duplicate_count": duplicate_count
    }

# ==================== 系统设置 API ====================

@router.get("/api/settings/version")
async def get_version_settings(
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取版本控制配置"""
    server_version = db.query(Config).filter(Config.key == "server_version").first()
    min_client_version = db.query(Config).filter(Config.key == "min_client_version").first()
    update_message = db.query(Config).filter(Config.key == "update_message").first()
    
    return {
        "server_version": server_version.value if server_version else "1.0.0",
        "min_client_version": min_client_version.value if min_client_version else "1.0.0",
        "update_message": update_message.value if update_message else "发现新版本，请立即更新客户端"
    }

@router.post("/api/settings/version")
async def update_version_settings(
    request: Request,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """更新版本控制配置"""
    # 接收 JSON 数据
    data = await request.json()
    server_version = data.get("server_version", "")
    min_client_version = data.get("min_client_version", "")
    update_message = data.get("update_message", "")
    
    # 验证版本号格式
    import re
    version_pattern = r'^\d+\.\d+\.\d+$'
    if not re.match(version_pattern, server_version):
        raise HTTPException(status_code=400, detail="服务器版本号格式不正确")
    if not re.match(version_pattern, min_client_version):
        raise HTTPException(status_code=400, detail="最低客户端版本格式不正确")
    
    # 更新或创建配置
    configs = [
        ("server_version", server_version, "服务器版本号"),
        ("min_client_version", min_client_version, "最低客户端版本号"),
        ("update_message", update_message, "更新提示消息")
    ]
    
    for key, value, desc in configs:
        config = db.query(Config).filter(Config.key == key).first()
        if config:
            config.value = value
            config.updated_at = datetime.utcnow()
        else:
            config = Config(key=key, value=value, description=desc)
            db.add(config)
    
    db.commit()
    
    return {
        "success": True,
        "message": "版本配置已更新"
    }

@router.get("/api/settings/firebase")
async def get_firebase_settings(
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取 Firebase API Key 配置"""
    firebase_key = db.query(Config).filter(Config.key == "firebase_api_key").first()
    
    # 获取环境变量中的配置（优先级更高）
    env_firebase_key = os.getenv("FIREBASE_API_KEY")
    
    return {
        "success": True,
        "firebase_api_key": firebase_key.value if firebase_key else "",
        "env_firebase_api_key": env_firebase_key if env_firebase_key else "",
        "using_env": bool(env_firebase_key),
        "message": "环境变量配置优先级更高" if env_firebase_key else "使用数据库配置"
    }

@router.post("/api/settings/firebase")
async def update_firebase_settings(
    request: Request,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """更新 Firebase API Key 配置"""
    form_data = await request.form()
    firebase_api_key = form_data.get("firebase_api_key", "").strip()
    
    if not firebase_api_key:
        raise HTTPException(status_code=400, detail="Firebase API Key 不能为空")
    
    # 验证 API Key 格式
    if not firebase_api_key.startswith("AIza") or len(firebase_api_key) != 39:
        raise HTTPException(
            status_code=400, 
            detail="Firebase API Key 格式不正确（应以 AIza 开头，共39个字符）"
        )
    
    # 更新或创建配置
    config = db.query(Config).filter(Config.key == "firebase_api_key").first()
    if config:
        config.value = firebase_api_key
        config.updated_at = datetime.utcnow()
    else:
        config = Config(
            key="firebase_api_key",
            value=firebase_api_key,
            description="Firebase API Key（用于账号登录）"
        )
        db.add(config)
    
    db.commit()
    
    # 检查是否有环境变量配置
    env_key = os.getenv("FIREBASE_API_KEY")
    warning = ""
    if env_key:
        warning = "注意：环境变量 FIREBASE_API_KEY 已配置，将优先使用环境变量的值"
    
    return {
        "success": True,
        "message": "Firebase API Key 已更新",
        "warning": warning
    }

@router.post("/api/settings/firebase/test")
async def test_firebase_key(
    request: Request,
    username: str = Depends(verify_admin)
):
    """测试 Firebase API Key 是否有效"""
    import httpx
    
    form_data = await request.form()
    firebase_api_key = form_data.get("firebase_api_key", "").strip()
    
    if not firebase_api_key:
        raise HTTPException(status_code=400, detail="Firebase API Key 不能为空")
    
    try:
        # 使用一个测试邮箱和密码测试 API Key
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}',
                json={
                    'email': 'test@example.com',
                    'password': 'testpassword',
                    'returnSecureToken': True,
                },
                headers={'Content-Type': 'application/json'}
            )
            
            # 如果返回 400 且错误是 EMAIL_NOT_FOUND 或 INVALID_PASSWORD，说明 API Key 有效
            if response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', '')
                
                if error_msg in ['EMAIL_NOT_FOUND', 'INVALID_PASSWORD', 'INVALID_EMAIL']:
                    return {
                        "success": True,
                        "valid": True,
                        "message": "Firebase API Key 有效"
                    }
                elif 'API key not valid' in error_msg:
                    return {
                        "success": True,
                        "valid": False,
                        "message": "Firebase API Key 无效"
                    }
                else:
                    return {
                        "success": True,
                        "valid": False,
                        "message": f"测试失败: {error_msg}"
                    }
            elif response.status_code == 200:
                # 不太可能，但如果成功了说明 Key 有效
                return {
                    "success": True,
                    "valid": True,
                    "message": "Firebase API Key 有效"
                }
            else:
                return {
                    "success": True,
                    "valid": False,
                    "message": f"测试失败: HTTP {response.status_code}"
                }
                
    except Exception as e:
        return {
            "success": True,
            "valid": False,
            "message": f"测试失败: {str(e)}"
        }

# ==================== Pro账号固定配置 ====================

@router.get("/api/settings/fixed-pro")
async def get_fixed_pro_settings(
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取固定Pro账号配置"""
    fixed_pro_email = db.query(Config).filter(Config.key == "fixed_pro_email").first()
    fixed_pro_password = db.query(Config).filter(Config.key == "fixed_pro_password").first()
    fixed_pro_name = db.query(Config).filter(Config.key == "fixed_pro_name").first()
    fixed_pro_api_key = db.query(Config).filter(Config.key == "fixed_pro_api_key").first()
    
    return {
        "fixed_pro_email": fixed_pro_email.value if fixed_pro_email else "",
        "fixed_pro_password": fixed_pro_password.value if fixed_pro_password else "",
        "fixed_pro_name": fixed_pro_name.value if fixed_pro_name else "ProUser",
        "fixed_pro_api_key": fixed_pro_api_key.value if fixed_pro_api_key else "",
        "has_password": bool(fixed_pro_password and fixed_pro_password.value)
    }

@router.post("/api/settings/fixed-pro")
async def update_fixed_pro_settings(
    request: Request,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """更新固定Pro账号配置"""
    form_data = await request.form()
    fixed_pro_email = form_data.get("fixed_pro_email", "").strip()
    fixed_pro_password = form_data.get("fixed_pro_password", "").strip()
    fixed_pro_name = form_data.get("fixed_pro_name", "").strip()
    fixed_pro_api_key = form_data.get("fixed_pro_api_key", "").strip()
    
    # 更新或创建配置
    configs_to_update = [
        ("fixed_pro_email", fixed_pro_email),
        ("fixed_pro_name", fixed_pro_name),
        ("fixed_pro_api_key", fixed_pro_api_key)
    ]
    
    # 密码只在非空时更新（避免误清空）
    if fixed_pro_password:
        configs_to_update.append(("fixed_pro_password", fixed_pro_password))
    
    for key, value in configs_to_update:
        config = db.query(Config).filter(Config.key == key).first()
        if config:
            config.value = value
        else:
            db.add(Config(key=key, value=value))
    
    db.commit()
    
    return {
        "success": True,
        "message": "Pro账号配置已更新"
    }

# ==================== 工具函数 ====================

def get_statistics(db: Session) -> StatsResponse:
    """获取统计信息"""
    total_accounts = db.query(Account).count()
    unused_accounts = db.query(Account).filter(Account.status == AccountStatus.unused).count()
    used_accounts = db.query(Account).filter(Account.status == AccountStatus.used).count()
    expired_accounts = db.query(Account).filter(Account.status == AccountStatus.expired).count()
    
    total_keys = db.query(Key).count()
    inactive_keys = db.query(Key).filter(Key.status == KeyStatus.inactive).count()
    active_keys = db.query(Key).filter(Key.status == KeyStatus.active).count()
    expired_keys = db.query(Key).filter(Key.status == KeyStatus.expired).count()
    
    # 计算已激活卡密未获取账号总和（仅限有限额度类型）
    # 公式：SUM(account_limit - request_count) for all active limited keys
    pending_demand = db.query(
        func.coalesce(
            func.sum(Key.account_limit - Key.request_count),
            0
        )
    ).filter(
        Key.status == KeyStatus.active,
        Key.key_type == KeyType.limited,
        Key.is_disabled == False
    ).scalar() or 0
    
    # Pro 账号统计（从 ProAccount 表查询）
    total_pro_accounts = db.query(ProAccount).count()
    unused_pro_accounts = db.query(ProAccount).filter(
        ProAccount.status == AccountStatus.unused
    ).count()
    used_pro_accounts = db.query(ProAccount).filter(
        ProAccount.status == AccountStatus.used
    ).count()
    expired_pro_accounts = db.query(ProAccount).filter(
        ProAccount.status == AccountStatus.expired
    ).count()
    
    # Pro 密钥统计
    total_pro_keys = db.query(Key).filter(Key.key_type == KeyType.pro).count()
    active_pro_keys = db.query(Key).filter(
        Key.key_type == KeyType.pro,
        Key.status == KeyStatus.active,
        Key.is_disabled == False
    ).count()
    
    # Pro 号池待获取需求（Pro类型密钥的剩余配额）
    pending_pro_demand = db.query(
        func.coalesce(
            func.sum(Key.account_limit - Key.request_count),
            0
        )
    ).filter(
        Key.status == KeyStatus.active,
        Key.key_type == KeyType.pro,
        Key.is_disabled == False,
        Key.account_limit > 0
    ).scalar() or 0
    
    return StatsResponse(
        total_accounts=total_accounts,
        unused_accounts=unused_accounts,
        used_accounts=used_accounts,
        expired_accounts=expired_accounts,
        total_keys=total_keys,
        inactive_keys=inactive_keys,
        active_keys=active_keys,
        expired_keys=expired_keys,
        pending_account_demand=max(0, pending_demand),
        total_pro_accounts=total_pro_accounts,
        unused_pro_accounts=unused_pro_accounts,
        used_pro_accounts=used_pro_accounts,
        expired_pro_accounts=expired_pro_accounts,
        total_pro_keys=total_pro_keys,
        active_pro_keys=active_pro_keys,
        pending_pro_demand=max(0, pending_pro_demand)
    )

# ==================== 公告管理 API ====================

@router.get("/api/announcements/list")
async def list_announcements(
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取所有公告列表"""
    announcements = db.query(Announcement).order_by(
        Announcement.created_at.desc()
    ).all()
    
    return {
        "success": True,
        "data": [
            {
                "id": a.id,
                "content": a.content,
                "is_active": a.is_active,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
                "created_by": a.created_by
            } for a in announcements
        ],
        "total": len(announcements)
    }

@router.post("/api/announcements/create")
async def create_announcement(
    content: str = Form(...),
    is_active: bool = Form(True),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """创建新公告"""
    try:
        # 如果新公告是启用状态，禁用所有其他公告
        if is_active:
            db.query(Announcement).update({"is_active": False})
        
        # 创建新公告
        announcement = Announcement(
            content=content,
            is_active=is_active,
            created_by=username,
            updated_by=username
        )
        
        db.add(announcement)
        db.commit()
        db.refresh(announcement)
        
        return {
            "success": True,
            "message": "公告创建成功",
            "data": {
                "id": announcement.id,
                "content": announcement.content,
                "is_active": announcement.is_active
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建公告失败: {str(e)}")

@router.post("/api/announcements/{announcement_id}/update")
async def update_announcement(
    announcement_id: int,
    content: str = Form(None),
    is_active: bool = Form(None),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """更新公告"""
    try:
        announcement = db.query(Announcement).filter(
            Announcement.id == announcement_id
        ).first()
        
        if not announcement:
            raise HTTPException(status_code=404, detail="公告不存在")
        
        # 如果要启用此公告，禁用其他公告
        if is_active:
            db.query(Announcement).filter(
                Announcement.id != announcement_id
            ).update({"is_active": False})
        
        # 更新字段
        if content is not None:
            announcement.content = content
        if is_active is not None:
            announcement.is_active = is_active
        
        announcement.updated_by = username
        announcement.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": "公告更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新公告失败: {str(e)}")

@router.post("/api/announcements/{announcement_id}/delete")
async def delete_announcement(
    announcement_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """删除公告"""
    try:
        announcement = db.query(Announcement).filter(
            Announcement.id == announcement_id
        ).first()
        
        if not announcement:
            raise HTTPException(status_code=404, detail="公告不存在")
        
        db.delete(announcement)
        db.commit()
        
        return {
            "success": True,
            "message": "公告删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除公告失败: {str(e)}")

@router.post("/api/announcements/{announcement_id}/toggle")
async def toggle_announcement(
    announcement_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """切换公告启用状态"""
    try:
        announcement = db.query(Announcement).filter(
            Announcement.id == announcement_id
        ).first()
        
        if not announcement:
            raise HTTPException(status_code=404, detail="公告不存在")
        
        # 切换状态
        new_status = not announcement.is_active
        
        # 如果要启用，禁用其他公告
        if new_status:
            db.query(Announcement).filter(
                Announcement.id != announcement_id
            ).update({"is_active": False})
        
        announcement.is_active = new_status
        announcement.updated_by = username
        announcement.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"公告已{'启用' if new_status else '禁用'}"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"切换公告状态失败: {str(e)}")

# ==================== 版本说明管理 ====================

@router.get("/version-notes", response_class=HTMLResponse)
async def version_notes_page(
    request: Request,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """版本说明管理页面"""
    notes = db.query(VersionNote).order_by(VersionNote.release_date.desc()).all()
    return templates.TemplateResponse("version_notes.html", {
        "request": request,
        "username": username,
        "notes": notes
    })

@router.get("/api/version-notes")
async def get_version_notes_api(
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取版本说明列表 API"""
    notes = db.query(VersionNote).order_by(VersionNote.release_date.desc()).all()
    return {
        "success": True,
        "data": [
            {
                "id": note.id,
                "version": note.version,
                "title": note.title,
                "content": note.content,
                "release_date": note.release_date.isoformat() if note.release_date else None,
                "is_published": note.is_published,
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None
            }
            for note in notes
        ]
    }

@router.post("/api/version-notes")
async def create_version_note(
    version: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    release_date: str = Form(None),
    is_published: bool = Form(True),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """创建版本说明"""
    try:
        # 解析发布日期
        parsed_date = None
        if release_date:
            try:
                parsed_date = datetime.fromisoformat(release_date.replace('Z', '+00:00'))
            except:
                parsed_date = datetime.utcnow()
        else:
            parsed_date = datetime.utcnow()
        
        note = VersionNote(
            version=version,
            title=title,
            content=content,
            release_date=parsed_date,
            is_published=is_published
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        
        return {"success": True, "message": "版本说明创建成功", "id": note.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建版本说明失败: {str(e)}")

@router.put("/api/version-notes/{note_id}")
async def update_version_note(
    note_id: int,
    version: str = Form(None),
    title: str = Form(None),
    content: str = Form(None),
    release_date: str = Form(None),
    is_published: bool = Form(None),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """更新版本说明"""
    try:
        note = db.query(VersionNote).filter(VersionNote.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="版本说明不存在")
        
        if version is not None:
            note.version = version
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        if release_date:
            try:
                note.release_date = datetime.fromisoformat(release_date.replace('Z', '+00:00'))
            except:
                pass
        if is_published is not None:
            note.is_published = is_published
        
        note.updated_at = datetime.utcnow()
        db.commit()
        
        return {"success": True, "message": "版本说明更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新版本说明失败: {str(e)}")

@router.delete("/api/version-notes/{note_id}")
async def delete_version_note(
    note_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """删除版本说明"""
    try:
        note = db.query(VersionNote).filter(VersionNote.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="版本说明不存在")
        
        db.delete(note)
        db.commit()
        
        return {"success": True, "message": "版本说明删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除版本说明失败: {str(e)}")

@router.post("/api/version-notes/{note_id}/toggle")
async def toggle_version_note(
    note_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """切换版本说明发布状态"""
    try:
        note = db.query(VersionNote).filter(VersionNote.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="版本说明不存在")
        
        note.is_published = not note.is_published
        note.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": f"版本说明已{'发布' if note.is_published else '取消发布'}"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"切换发布状态失败: {str(e)}")


# ==================== 插件管理 ====================

@router.get("/plugins", response_class=HTMLResponse)
async def plugins_page(request: Request, username: str = Depends(verify_admin)):
    """插件管理页面"""
    return templates.TemplateResponse("plugins.html", {"request": request})

@router.get("/api/plugins")
async def get_plugins(
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取所有插件列表"""
    try:
        plugins = db.query(PluginInfo).order_by(PluginInfo.updated_at.desc()).all()
        return {
            "success": True,
            "plugins": [
                {
                    "id": p.id,
                    "plugin_name": p.plugin_name,
                    "display_name": p.display_name,
                    "description": p.description,
                    "ide_type": p.ide_type,
                    "current_version": p.current_version,
                    "min_version": p.min_version,
                    "download_url": p.download_url,
                    "changelog": p.changelog,
                    "update_title": p.update_title,
                    "update_description": p.update_description,
                    "is_force_update": p.is_force_update,
                    "is_active": p.is_active,
                    "is_primary": p.is_primary,
                    "file_size": p.file_size,
                    "icon": p.icon,
                    "icon_gradient": p.icon_gradient,
                    "features": p.features,
                    "usage_steps": p.usage_steps,
                    "tips": p.tips,
                    "mcp_config_path": p.mcp_config_path,
                    "extensions_path": p.extensions_path,
                    "mcp_extra_config": p.mcp_extra_config,
                    "sort_order": p.sort_order,
                    "release_date": p.release_date.isoformat() if p.release_date else None,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None
                }
                for p in plugins
            ],
            "total": len(plugins)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取插件列表失败: {str(e)}")

@router.post("/api/plugins")
async def create_plugin(
    plugin_name: str = Form(...),
    current_version: str = Form(...),
    download_url: str = Form(...),
    # 基础字段
    display_name: str = Form(None),
    description: str = Form(None),
    ide_type: str = Form('windsurf'),
    min_version: str = Form(None),
    changelog: str = Form(None),
    update_title: str = Form(None),
    update_description: str = Form(None),
    is_force_update: str = Form('false'),  # 改为 str 以正确处理 "true"/"false"
    is_active: str = Form('true'),  # 改为 str 以正确处理 "true"/"false"
    is_primary: str = Form('false'),  # 改为 str 以正确处理 "true"/"false"
    file_size: str = Form(None),
    sort_order: int = Form(0),
    # 客户端展示字段
    icon: str = Form(None),
    icon_gradient: str = Form(None),
    features: str = Form(None),
    usage_steps: str = Form(None),
    tips: str = Form(None),
    mcp_config_path: str = Form(None),
    extensions_path: str = Form(None),
    mcp_extra_config: str = Form(None),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """创建新插件"""
    try:
        # 检查是否已存在同名插件
        existing = db.query(PluginInfo).filter(PluginInfo.plugin_name == plugin_name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"插件 {plugin_name} 已存在")
        
        # 解析JSON字段
        import json
        def parse_json_field(value):
            if not value or not value.strip():
                return None
            try:
                return json.loads(value)
            except:
                return None
        
        # 解析布尔字段（处理 "true"/"false" 字符串）
        def parse_bool_field(value, default=False):
            if value is None:
                return default
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        
        plugin = PluginInfo(
            plugin_name=plugin_name,
            display_name=display_name if display_name and display_name.strip() else None,
            description=description if description and description.strip() else None,
            ide_type=ide_type or 'windsurf',
            current_version=current_version,
            min_version=min_version if min_version and min_version.strip() else None,
            download_url=download_url,
            changelog=changelog if changelog and changelog.strip() else None,
            update_title=update_title if update_title and update_title.strip() else None,
            update_description=update_description if update_description and update_description.strip() else None,
            is_force_update=parse_bool_field(is_force_update, False),
            is_active=parse_bool_field(is_active, True),
            is_primary=parse_bool_field(is_primary, False),
            file_size=file_size if file_size and file_size.strip() else None,
            icon=icon if icon and icon.strip() else 'shield-check',
            icon_gradient=parse_json_field(icon_gradient),
            features=parse_json_field(features),
            usage_steps=parse_json_field(usage_steps),
            tips=parse_json_field(tips),
            mcp_config_path=mcp_config_path if mcp_config_path and mcp_config_path.strip() else None,
            extensions_path=extensions_path if extensions_path and extensions_path.strip() else None,
            mcp_extra_config=parse_json_field(mcp_extra_config),
            sort_order=sort_order or 0,
            release_date=datetime.utcnow()
        )
        
        db.add(plugin)
        db.commit()
        
        return {"success": True, "message": "插件创建成功", "id": plugin.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建插件失败: {str(e)}")

@router.put("/api/plugins/{plugin_id}")
async def update_plugin(
    plugin_id: int,
    plugin_name: str = Form(None),
    current_version: str = Form(None),
    download_url: str = Form(None),
    # 基础字段
    display_name: str = Form(None),
    description: str = Form(None),
    ide_type: str = Form(None),
    min_version: str = Form(None),
    changelog: str = Form(None),
    update_title: str = Form(None),
    update_description: str = Form(None),
    is_force_update: str = Form(None),  # 改为 str 以正确处理 "true"/"false"
    is_active: str = Form(None),  # 改为 str 以正确处理 "true"/"false"
    is_primary: str = Form(None),  # 改为 str 以正确处理 "true"/"false"
    file_size: str = Form(None),
    sort_order: int = Form(None),
    # 客户端展示字段
    icon: str = Form(None),
    icon_gradient: str = Form(None),
    features: str = Form(None),
    usage_steps: str = Form(None),
    tips: str = Form(None),
    mcp_config_path: str = Form(None),
    extensions_path: str = Form(None),
    mcp_extra_config: str = Form(None),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """更新插件信息"""
    try:
        plugin = db.query(PluginInfo).filter(PluginInfo.id == plugin_id).first()
        if not plugin:
            raise HTTPException(status_code=404, detail="插件不存在")
        
        # 解析JSON字段（只有有效JSON才更新，空字符串保持原值）
        import json
        def parse_json_field(value, current_value=None):
            if value is None:
                return current_value  # 未提供时保持原值
            if not value or not value.strip():
                return current_value  # 空字符串保持原值
            try:
                return json.loads(value)
            except:
                return current_value  # JSON解析失败保持原值
        
        # 解析布尔字段（处理 "true"/"false" 字符串）
        def parse_bool_field(value):
            if value is None:
                return None
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        
        # 更新基础字段（只有非空时才更新）
        if plugin_name is not None and plugin_name.strip():
            plugin.plugin_name = plugin_name
        if display_name is not None:
            plugin.display_name = display_name if display_name.strip() else None
        if description is not None:
            plugin.description = description if description.strip() else None
        if ide_type is not None and ide_type.strip():
            plugin.ide_type = ide_type
        if current_version is not None and current_version.strip():
            plugin.current_version = current_version
            plugin.release_date = datetime.utcnow()  # 更新版本时更新发布日期
        if download_url is not None and download_url.strip():
            plugin.download_url = download_url
        if min_version is not None:
            plugin.min_version = min_version if min_version.strip() else None
        if changelog is not None:
            plugin.changelog = changelog if changelog.strip() else None
        if update_title is not None:
            plugin.update_title = update_title if update_title.strip() else None
        if update_description is not None:
            plugin.update_description = update_description if update_description.strip() else None
        
        # 更新布尔字段
        if is_force_update is not None:
            plugin.is_force_update = parse_bool_field(is_force_update)
        if is_active is not None:
            plugin.is_active = parse_bool_field(is_active)
        if is_primary is not None:
            plugin.is_primary = parse_bool_field(is_primary)
        
        if file_size is not None:
            plugin.file_size = file_size if file_size.strip() else None
        if sort_order is not None:
            plugin.sort_order = sort_order
        if icon is not None:
            plugin.icon = icon if icon.strip() else 'shield-check'
        
        # 更新JSON字段（保持原值如果新值无效）
        if icon_gradient is not None:
            plugin.icon_gradient = parse_json_field(icon_gradient, plugin.icon_gradient)
        if features is not None:
            plugin.features = parse_json_field(features, plugin.features)
        if usage_steps is not None:
            plugin.usage_steps = parse_json_field(usage_steps, plugin.usage_steps)
        if tips is not None:
            plugin.tips = parse_json_field(tips, plugin.tips)
        if mcp_config_path is not None:
            plugin.mcp_config_path = mcp_config_path if mcp_config_path.strip() else None
        if extensions_path is not None:
            plugin.extensions_path = extensions_path if extensions_path.strip() else None
        if mcp_extra_config is not None:
            plugin.mcp_extra_config = parse_json_field(mcp_extra_config, plugin.mcp_extra_config)
        
        plugin.updated_at = datetime.utcnow()
        db.commit()
        
        return {"success": True, "message": "插件更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新插件失败: {str(e)}")

@router.delete("/api/plugins/{plugin_id}")
async def delete_plugin(
    plugin_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """删除插件"""
    try:
        plugin = db.query(PluginInfo).filter(PluginInfo.id == plugin_id).first()
        if not plugin:
            raise HTTPException(status_code=404, detail="插件不存在")
        
        db.delete(plugin)
        db.commit()
        
        return {"success": True, "message": "插件删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除插件失败: {str(e)}")

@router.post("/api/plugins/{plugin_id}/toggle")
async def toggle_plugin(
    plugin_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """切换插件启用状态"""
    try:
        plugin = db.query(PluginInfo).filter(PluginInfo.id == plugin_id).first()
        if not plugin:
            raise HTTPException(status_code=404, detail="插件不存在")
        
        plugin.is_active = not plugin.is_active
        plugin.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": f"插件已{'启用' if plugin.is_active else '禁用'}"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"切换插件状态失败: {str(e)}")

# ==================== 设备绑定管理 ====================

@router.get("/api/keys/{key_code}/devices")
async def get_key_devices(
    key_code: str,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取指定卡密的设备绑定列表"""
    try:
        # 验证卡密是否存在
        key = db.query(Key).filter(Key.key_code == key_code).first()
        if not key:
            raise HTTPException(status_code=404, detail="卡密不存在")
        
        # 查询设备绑定
        devices = db.query(DeviceBinding).filter(
            DeviceBinding.key_code == key_code,
            DeviceBinding.is_active == True
        ).order_by(DeviceBinding.last_active_at.desc()).all()
        
        # 格式化返回数据
        device_list = []
        for device in devices:
            device_list.append({
                "id": device.id,
                "device_id": device.device_id,
                "device_name": device.device_name or "未命名设备",
                "first_bound_at": device.first_bound_at.strftime("%Y-%m-%d %H:%M:%S"),
                "last_active_at": device.last_active_at.strftime("%Y-%m-%d %H:%M:%S"),
                "request_count": device.request_count,
                "is_active": device.is_active
            })
        
        return {
            "success": True,
            "key_code": key_code,
            "max_devices": key.max_devices if hasattr(key, 'max_devices') else 3,
            "device_count": len(device_list),
            "devices": device_list
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取设备列表失败: {str(e)}")

@router.post("/api/keys/{key_code}/devices/unbind")
async def unbind_device(
    key_code: str,
    device_id: str = Form(...),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """管理员强制解绑设备"""
    try:
        # 验证卡密是否存在
        key = db.query(Key).filter(Key.key_code == key_code).first()
        if not key:
            raise HTTPException(status_code=404, detail="卡密不存在")
        
        # 查找设备绑定
        binding = db.query(DeviceBinding).filter(
            DeviceBinding.key_code == key_code,
            DeviceBinding.device_id == device_id,
            DeviceBinding.is_active == True
        ).first()
        
        if not binding:
            raise HTTPException(status_code=404, detail="设备绑定不存在或已解绑")
        
        # 标记为不活跃（软删除）
        binding.is_active = False
        db.commit()
        
        return {
            "success": True,
            "message": "设备解绑成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"解绑设备失败: {str(e)}")

@router.put("/api/keys/{key_code}/max-devices")
async def update_max_devices(
    key_code: str,
    max_devices: int = Form(...),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """更新卡密的最大设备绑定数"""
    try:
        # 验证参数
        if max_devices < 1 or max_devices > 10:
            raise HTTPException(status_code=400, detail="设备数量必须在 1-10 之间")
        
        # 查找卡密
        key = db.query(Key).filter(Key.key_code == key_code).first()
        if not key:
            raise HTTPException(status_code=404, detail="卡密不存在")
        
        # 更新 max_devices
        if hasattr(key, 'max_devices'):
            key.max_devices = max_devices
        else:
            raise HTTPException(status_code=500, detail="数据库缺少 max_devices 字段，请先运行迁移脚本")
        
        db.commit()
        
        return {
            "success": True,
            "message": f"最大设备数已更新为 {max_devices}",
            "max_devices": max_devices
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


# ==================== 团队管理 ====================

from app.models import TeamConfig, TeamMember, MemberSwitchHistory

@router.get("/teams", response_class=HTMLResponse)
async def teams_page(request: Request, username: str = Depends(verify_admin)):
    """团队管理页面"""
    return templates.TemplateResponse("teams.html", {"request": request})


@router.get("/api/teams")
async def get_teams(
    search: str = None,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取团队列表"""
    query = db.query(TeamConfig)
    
    if search:
        query = query.filter(
            (TeamConfig.name.ilike(f"%{search}%")) |
            (TeamConfig.admin_email.ilike(f"%{search}%"))
        )
    
    teams = query.order_by(TeamConfig.created_at.desc()).all()
    
    # 统计每个团队的成员数
    result = []
    for team in teams:
        member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
        team_dict = {
            "id": team.id,
            "name": team.name,
            "admin_email": team.admin_email,
            "is_active": team.is_active,
            "credits_threshold": team.credits_threshold,
            "check_interval_minutes": team.check_interval_minutes,
            "current_member_id": team.current_member_id,
            "switch_count": team.switch_count,
            "created_at": team.created_at.isoformat() if team.created_at else None,
            "member_count": member_count
        }
        result.append(team_dict)
    
    return {"success": True, "teams": result}


@router.post("/api/teams")
async def create_team(
    request: Request,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """创建团队（多个Pro卡密可关联到同一个团队，通过卡密的team_id字段）"""
    data = await request.json()
    
    # 检查是否已存在同名团队
    existing = db.query(TeamConfig).filter(
        TeamConfig.name == data.get("name")
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已存在同名团队")
    
    team = TeamConfig(
        name=data.get("name"),
        admin_email=data.get("admin_email"),
        admin_password=data.get("admin_password"),
        credits_threshold=data.get("credits_threshold", 20),
        check_interval_minutes=data.get("check_interval_minutes", 5)
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    
    return {"success": True, "message": "创建成功", "id": team.id}


@router.put("/api/teams/{team_id}")
async def update_team(
    team_id: int,
    request: Request,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """更新团队"""
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    data = await request.json()
    
    if data.get("name"):
        team.name = data["name"]
    if data.get("admin_email"):
        team.admin_email = data["admin_email"]
    if data.get("admin_password"):
        team.admin_password = data["admin_password"]
    if data.get("credits_threshold") is not None:
        team.credits_threshold = data["credits_threshold"]
    if data.get("check_interval_minutes") is not None:
        team.check_interval_minutes = data["check_interval_minutes"]
    if data.get("is_active") is not None:
        team.is_active = data["is_active"]
    
    db.commit()
    return {"success": True, "message": "更新成功"}


@router.delete("/api/teams/{team_id}")
async def delete_team(
    team_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """删除团队及其所有成员"""
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    # 删除成员
    db.query(TeamMember).filter(TeamMember.team_id == team_id).delete()
    # 删除切换历史
    db.query(MemberSwitchHistory).filter(MemberSwitchHistory.team_id == team_id).delete()
    # 删除团队
    db.delete(team)
    db.commit()
    
    return {"success": True, "message": "删除成功"}


@router.get("/api/teams/{team_id}/members")
async def get_team_members(
    team_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取团队成员列表"""
    members = db.query(TeamMember).filter(
        TeamMember.team_id == team_id
    ).order_by(TeamMember.sort_order).all()
    
    result = []
    for m in members:
        result.append({
            "id": m.id,
            "team_id": m.team_id,
            "email": m.email,
            "name": m.name,
            "is_enabled": m.is_enabled,
            "is_current": m.is_current,
            "is_exhausted": m.is_exhausted,
            "last_credits": m.last_credits,
            "sort_order": m.sort_order,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
    
    return {"success": True, "members": result}


@router.post("/api/teams/{team_id}/members")
async def add_team_member(
    team_id: int,
    request: Request,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """添加团队成员"""
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    data = await request.json()
    
    # 检查邮箱是否已存在
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.email == data.get("email")
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该成员已存在")
    
    member = TeamMember(
        team_id=team_id,
        email=data.get("email"),
        password=data.get("password"),
        name=data.get("name"),
        api_key=data.get("api_key"),
        sort_order=data.get("sort_order", 0)
    )
    db.add(member)
    db.commit()
    
    return {"success": True, "message": "添加成功", "id": member.id}


@router.put("/api/teams/{team_id}/members/{member_id}")
async def update_team_member(
    team_id: int,
    member_id: int,
    request: Request,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """更新团队成员"""
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.team_id == team_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    data = await request.json()
    
    if data.get("email"):
        member.email = data["email"]
    if data.get("password"):
        member.password = data["password"]
    if data.get("name") is not None:
        member.name = data["name"]
    if data.get("api_key") is not None:
        member.api_key = data["api_key"]
    if data.get("sort_order") is not None:
        member.sort_order = data["sort_order"]
    
    db.commit()
    return {"success": True, "message": "更新成功"}


@router.delete("/api/teams/{team_id}/members/{member_id}")
async def delete_team_member(
    team_id: int,
    member_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """删除团队成员"""
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.team_id == team_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    db.delete(member)
    db.commit()
    
    return {"success": True, "message": "删除成功"}


@router.get("/api/teams/{team_id}/history")
async def get_team_switch_history(
    team_id: int,
    limit: int = 50,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """获取切换历史"""
    history = db.query(MemberSwitchHistory).filter(
        MemberSwitchHistory.team_id == team_id
    ).order_by(MemberSwitchHistory.switched_at.desc()).limit(limit).all()
    
    result = []
    for h in history:
        result.append({
            "id": h.id,
            "from_email": h.from_email,
            "to_email": h.to_email,
            "reason": h.reason,
            "credits_before": h.credits_before,
            "switched_at": h.switched_at.isoformat() if h.switched_at else None
        })
    
    return {"success": True, "history": result}


@router.post("/api/teams/{team_id}/set-current/{member_id}")
async def set_current_member(
    team_id: int,
    member_id: int,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """设置当前成员"""
    team = db.query(TeamConfig).filter(TeamConfig.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    new_member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.team_id == team_id
    ).first()
    if not new_member:
        raise HTTPException(status_code=404, detail="成员不存在")
    
    # 获取当前成员
    current_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.is_current == True
    ).first()
    
    # 更新状态
    if current_member and current_member.id != member_id:
        current_member.is_current = False
        current_member.is_enabled = False
        current_member.disabled_at = datetime.utcnow()
    
    new_member.is_current = True
    new_member.is_enabled = True
    new_member.enabled_at = datetime.utcnow()
    
    team.current_member_id = member_id
    team.last_switch_at = datetime.utcnow()
    team.switch_count += 1
    
    # 记录切换历史
    history = MemberSwitchHistory(
        team_id=team_id,
        from_member_id=current_member.id if current_member else None,
        to_member_id=member_id,
        from_email=current_member.email if current_member else None,
        to_email=new_member.email,
        reason="管理员手动切换",
        credits_before=current_member.last_credits if current_member else None
    )
    db.add(history)
    
    # 更新固定Pro账号配置
    from app.models import Config
    email_config = db.query(Config).filter(Config.key == "fixed_pro_email").first()
    if email_config:
        email_config.value = new_member.email
    else:
        db.add(Config(key="fixed_pro_email", value=new_member.email))
    
    password_config = db.query(Config).filter(Config.key == "fixed_pro_password").first()
    if password_config:
        password_config.value = new_member.password
    else:
        db.add(Config(key="fixed_pro_password", value=new_member.password))
    
    db.commit()
    
    return {"success": True, "message": f"已切换到成员: {new_member.email}"}
