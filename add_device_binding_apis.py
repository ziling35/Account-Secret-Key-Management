"""
在 admin.py 文件末尾添加以下设备绑定管理 API
"""

API_CODE = '''
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

@router.post("/api/keys/create")
async def create_keys(
    count: int,
    key_type: str,
    duration_days: int,
    notes: str = "",
    account_limit: int = 0,
    max_devices: int = 3,  # 新增参数：最大设备数，默认3
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """批量创建密钥（已更新，支持设置 max_devices）"""
    if count <= 0 or count > 100:
        raise HTTPException(status_code=400, detail="数量必须在1-100之间")
    
    if key_type not in ["unlimited", "limited", "pro"]:
        raise HTTPException(status_code=400, detail="密钥类型必须为 unlimited、limited 或 pro")
    
    if duration_days <= 0:
        raise HTTPException(status_code=400, detail="有效期必须大于0天")
    
    if account_limit < -1:
        raise HTTPException(status_code=400, detail="账号配额无效（-1=不限制, 0=仅授权不含账号, >0=固定配额）")
    
    if max_devices < 1 or max_devices > 10:
        raise HTTPException(status_code=400, detail="设备数量必须在 1-10 之间")
    
    # 验证无限额度类型
    if key_type == "unlimited" and account_limit > 0:
        raise HTTPException(status_code=400, detail="无限额度类型的账号配额必须为0")
    
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
            notes=notes,
            account_limit=account_limit,
            max_devices=max_devices  # 设置最大设备数
        )
        db.add(key)
        keys.append(key_code)
    
    db.commit()
    
    return {
        "success": True,
        "count": len(keys),
        "keys": keys,
        "preview": "\\n".join(keys)
    }
'''

print("=" * 60)
print("设备绑定管理 API 代码")
print("=" * 60)
print("\n请将以下代码添加到 app/routers/admin.py 文件的末尾：\n")
print(API_CODE)
print("\n" + "=" * 60)
print("注意事项：")
print("1. 需要先运行数据库迁移脚本添加 max_devices 字段")
print("2. 需要导入 DeviceBinding 模型（已完成）")
print("3. 需要更新前端页面以调用这些 API")
print("=" * 60)
