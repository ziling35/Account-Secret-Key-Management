# 删除卡密功能说明

## 功能概述

为管理后台添加了删除密钥（卡密）的功能，允许管理员删除不需要的密钥。

---

## 实现内容

### 1. 后端 API (`app/routers/admin.py`)

#### 新增 API 端点

**路由**: `DELETE /admin/api/keys/delete/{key_id}`

**功能**: 删除指定 ID 的密钥

**权限**: 需要管理员登录

**参数**:
- `key_id` (路径参数): 要删除的密钥 ID

**返回**:
```json
{
  "success": true,
  "message": "密钥 abc12345... 已删除",
  "key_id": 123,
  "key_code": "abc123456789...",
  "old_status": "inactive"
}
```

**错误处理**:
- 404: 密钥不存在
- 401: 未授权（未登录）

#### 代码实现

```python
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
```

---

### 2. 前端界面 (`app/templates/keys.html`)

#### UI 变更

在密钥列表表格中新增"**操作**"列（固定在右侧）：

```html
<el-table-column label="操作" width="100" align="center" fixed="right">
    <template #default="scope">
        <el-button 
            link 
            type="danger" 
            size="small"
            @click="handleDelete(scope.row)"
            title="删除密钥">
            删除
        </el-button>
    </template>
</el-table-column>
```

#### 删除逻辑

```javascript
const handleDelete = async (row) => {
    try {
        // 二次确认对话框
        await ElementPlus.ElMessageBox.confirm(
            `确定要删除密钥 ${row.key_code.substring(0, 8)}... 吗？此操作不可恢复！`,
            '删除确认',
            {
                confirmButtonText: '确定删除',
                cancelButtonText: '取消',
                type: 'warning',
                confirmButtonClass: 'el-button--danger'
            }
        );

        // 发送删除请求
        const response = await axios.delete(`/admin/api/keys/delete/${row.id}`);
        
        ElMessage.success(response.data.message || '删除成功');
        
        // 重新加载列表
        loadKeys();
    } catch (error) {
        if (error !== 'cancel') {
            ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message));
        }
    }
};
```

---

## 使用方法

### 管理员操作步骤

1. **登录管理后台**
   - 访问 `/admin/login`
   - 使用管理员账号登录

2. **进入密钥管理页面**
   - 点击左侧菜单"密钥管理"
   - 或访问 `/admin/keys`

3. **删除密钥**
   - 在密钥列表中找到要删除的密钥
   - 点击最右侧"操作"列的"**删除**"按钮
   - 在弹出的确认对话框中点击"**确定删除**"
   - 系统提示删除成功，列表自动刷新

---

## 安全特性

### 1. 二次确认
- 点击删除按钮后会弹出确认对话框
- 显示要删除的密钥前 8 位（方便识别）
- 提示"此操作不可恢复"

### 2. 权限验证
- 必须以管理员身份登录才能访问删除 API
- 使用 `Depends(verify_admin)` 验证权限

### 3. 错误处理
- 密钥不存在时返回 404 错误
- 删除失败时显示友好的错误提示
- 取消删除操作时不显示错误（静默处理）

---

## 数据库操作

### 删除机制

使用 SQLAlchemy ORM 的 `delete` 方法：

```python
db.delete(key)  # 标记为删除
db.commit()     # 提交事务，真正删除
```

### 数据完整性

- **物理删除**: 从数据库中永久删除记录
- **不可恢复**: 删除后无法还原
- **级联关系**: 如果有外键关联，需要注意级联删除设置

**注意**: 当前实现是物理删除，如果需要保留删除记录用于审计，建议改为软删除（添加 `deleted_at` 字段）。

---

## 界面效果

### 操作列显示

```
┌───────────┬────────┬──────┬────────┬────┐
│ 密钥代码   │ 状态   │ 类型  │ ...   │ 操作│
├───────────┼────────┼──────┼────────┼────┤
│ abc12345..│ 未激活 │ 有限  │ ...   │删除 │
│ def67890..│ 已激活 │ 无限  │ ...   │删除 │
└───────────┴────────┴──────┴────────┴────┘
```

### 确认对话框

```
┌─────────────────────────────────┐
│           ⚠ 删除确认            │
├─────────────────────────────────┤
│ 确定要删除密钥 abc12345... 吗？  │
│ 此操作不可恢复！                 │
├─────────────────────────────────┤
│        [取消]  [确定删除]        │
└─────────────────────────────────┘
```

---

## 常见场景

### 1. 删除测试密钥
管理员创建测试密钥后，可以随时删除清理

### 2. 删除过期密钥
清理已过期且不再需要的密钥记录

### 3. 删除重复密钥
如果误创建重复密钥，可以删除多余的

### 4. 批量清理
配合筛选功能，可以快速定位并删除特定类型的密钥

---

## 扩展建议

### 1. 批量删除
可以添加批量选择和删除功能：
```javascript
// 添加复选框列
<el-table-column type="selection" width="55" />

// 批量删除按钮
<el-button type="danger" @click="handleBatchDelete">批量删除</el-button>
```

### 2. 软删除
为了数据安全和审计需求，可以改为软删除：
```python
# 在 Key 模型中添加字段
deleted_at = Column(DateTime, nullable=True)

# 删除时设置时间而不是真正删除
key.deleted_at = datetime.utcnow()
db.commit()

# 查询时过滤已删除记录
db.query(Key).filter(Key.deleted_at == None)
```

### 3. 删除日志
记录删除操作，方便审计：
```python
# 创建删除日志表
class DeleteLog(Base):
    __tablename__ = "delete_logs"
    
    id = Column(Integer, primary_key=True)
    deleted_type = Column(String)  # "key" or "account"
    deleted_id = Column(Integer)
    deleted_code = Column(String)
    deleted_by = Column(String)  # 管理员用户名
    deleted_at = Column(DateTime)
    reason = Column(String, nullable=True)
```

### 4. 删除限制
某些情况下可能需要禁止删除：
```python
# 禁止删除已激活的密钥
if key.status == KeyStatus.active:
    raise HTTPException(status_code=400, detail="已激活的密钥不能删除")

# 禁止删除有使用记录的密钥
if key.request_count > 0:
    raise HTTPException(status_code=400, detail="已使用的密钥不能删除")
```

---

## 测试建议

### 1. 功能测试
- ✅ 删除未激活的密钥
- ✅ 删除已激活的密钥
- ✅ 删除已过期的密钥
- ✅ 删除不存在的密钥（应返回 404）
- ✅ 取消删除操作

### 2. 权限测试
- ✅ 未登录时尝试删除（应返回 401）
- ✅ 普通用户登录时尝试删除（应拒绝）
- ✅ 管理员登录时删除（应成功）

### 3. UI 测试
- ✅ 确认对话框显示正确
- ✅ 删除成功后列表刷新
- ✅ 删除按钮样式正确（红色）
- ✅ 错误提示友好

---

## 更新日志

**v1.0.0 (2024-12-05)**
- ✅ 新增删除密钥 API 端点
- ✅ 前端添加删除按钮和确认对话框
- ✅ 实现二次确认机制
- ✅ 添加权限验证
- ✅ 完善错误处理

---

## 总结

删除卡密功能已完整实现，具备以下特点：

1. **安全**: 二次确认 + 权限验证
2. **友好**: 清晰的提示和错误处理
3. **高效**: 删除后自动刷新列表
4. **可扩展**: 易于添加批量删除、软删除等功能

管理员现在可以方便地管理和清理密钥数据。
