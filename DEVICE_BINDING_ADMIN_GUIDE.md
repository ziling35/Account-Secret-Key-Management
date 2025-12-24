# 设备绑定管理功能使用指南

## 📋 功能概述

为后端管理系统添加了完整的设备绑定信息展示和管理功能，管理员可以：
- 在卡密列表中查看每个卡密的设备绑定情况
- 查看设备绑定详情（设备列表、绑定时间、活跃时间等）
- 管理设备绑定数量限制（max_devices）
- 强制解绑设备

---

## 🎯 设备绑定判断逻辑

### 核心原理

1. **设备识别**：通过 `X-Device-ID` 请求头传递设备唯一标识（机器码）
2. **绑定限制**：每个卡密有 `max_devices` 字段控制最大绑定设备数（默认3台）
3. **自动绑定**：
   - 首次使用时自动绑定当前设备
   - 已绑定设备访问时更新 `last_active_at` 时间
4. **超限拒绝**：当绑定设备数达到 `max_devices` 上限时，拒绝新设备访问

### 数据库表结构

#### device_bindings 表
```sql
CREATE TABLE device_bindings (
    id SERIAL PRIMARY KEY,
    key_code VARCHAR NOT NULL,           -- 卡密代码
    device_id VARCHAR NOT NULL,          -- 设备唯一标识（机器码）
    device_name VARCHAR,                 -- 设备名称（可选）
    first_bound_at TIMESTAMP NOT NULL,   -- 首次绑定时间
    last_active_at TIMESTAMP NOT NULL,   -- 最后活跃时间
    request_count INTEGER DEFAULT 0,     -- 请求次数
    is_active BOOLEAN DEFAULT TRUE       -- 是否活跃
);
```

#### keys 表新增字段
```sql
ALTER TABLE keys 
ADD COLUMN max_devices INTEGER DEFAULT 3 NOT NULL;
```

---

## 🚀 使用指南

### 1. 查看设备绑定信息

#### 在卡密列表中查看

1. 进入 **密钥管理** 页面
2. 在 **显示列** 下拉菜单中勾选 **设备绑定**
3. 表格中会显示每个卡密的设备绑定情况：
   - 格式：`已绑定数/最大设备数`（例如：2/3）
   - 颜色标识：
     - 🔵 蓝色（info）：未绑定任何设备（0/3）
     - 🟢 绿色（success）：正常范围（1/3）
     - 🟡 黄色（warning）：接近上限（2/3，≥80%）
     - 🔴 红色（danger）：已达上限（3/3）

#### 查看设备详情

1. 点击卡密行的 **详情** 按钮
2. 弹出 **设备绑定详情** 对话框，显示：
   - 卡密代码
   - 已绑定设备数/最大设备数
   - 设备列表（包含设备名称、设备ID、首次绑定时间、最后活跃时间、请求次数）

---

### 2. 管理设备绑定数量

#### 修改最大设备数

1. 在 **设备绑定详情** 对话框中，点击 **修改最大设备数** 按钮
2. 在弹出的对话框中设置新的最大设备数（1-10台）
3. 点击 **确定** 保存

**注意**：
- 最大设备数范围：1-10台
- 修改后立即生效
- 如果当前绑定数已超过新设置的上限，不会自动解绑，但会阻止新设备绑定

---

### 3. 强制解绑设备

#### 解绑单个设备

1. 在 **设备绑定详情** 对话框中，找到要解绑的设备
2. 点击该设备行的 **解绑** 按钮
3. 确认解绑操作

**效果**：
- 设备被标记为不活跃（`is_active = false`）
- 该设备下次访问时需要重新绑定
- 如果已达绑定上限，解绑后可以绑定新设备

---

### 4. 创建卡密时设置设备数

在创建卡密时，可以设置 `max_devices` 参数（需要更新创建表单）：

```javascript
// 在创建卡密的表单中添加
{
    key_type: 'limited',
    count: 10,
    duration_days: 30,
    account_limit: 5,
    max_devices: 3,  // 设置最大设备数
    notes: ''
}
```

---

## 🔧 API 接口说明

### 1. 获取卡密设备列表

```http
GET /admin/api/keys/{key_code}/devices
```

**响应示例**：
```json
{
    "success": true,
    "key_code": "ABC123",
    "max_devices": 3,
    "device_count": 2,
    "devices": [
        {
            "id": 1,
            "device_id": "abc123...",
            "device_name": "DESKTOP-PC",
            "first_bound_at": "2024-01-01 10:00:00",
            "last_active_at": "2024-01-15 15:30:00",
            "request_count": 150,
            "is_active": true
        }
    ]
}
```

---

### 2. 强制解绑设备

```http
POST /admin/api/keys/{key_code}/devices/unbind
Content-Type: multipart/form-data

device_id: abc123...
```

**响应示例**：
```json
{
    "success": true,
    "message": "设备解绑成功"
}
```

---

### 3. 更新最大设备数

```http
PUT /admin/api/keys/{key_code}/max-devices
Content-Type: multipart/form-data

max_devices: 5
```

**响应示例**：
```json
{
    "success": true,
    "message": "最大设备数已更新为 5",
    "max_devices": 5
}
```

---

### 4. 卡密列表接口（已更新）

```http
GET /admin/api/keys/list?page=1&page_size=10
```

**响应中新增字段**：
```json
{
    "keys": [
        {
            "key_code": "ABC123",
            "device_count": 2,      // 新增：已绑定设备数
            "max_devices": 3,       // 新增：最大设备数
            // ... 其他字段
        }
    ]
}
```

---

## 📊 前端实现说明

### 新增的 Vue 组件

#### 1. 设备绑定列（表格列）

```html
<el-table-column v-if="visibleColumns.includes('device_binding')" label="设备绑定" width="140">
    <template #default="scope">
        <el-tag :type="getDeviceBindingType(scope.row)" size="small">
            {{ scope.row.device_count || 0 }}/{{ scope.row.max_devices || 3 }}
        </el-tag>
        <el-button link type="primary" @click="handleViewDevices(scope.row)">
            详情
        </el-button>
    </template>
</el-table-column>
```

#### 2. 设备绑定详情对话框

显示设备列表，支持查看和解绑操作。

#### 3. 修改最大设备数对话框

允许管理员修改卡密的最大设备绑定数量。

---

### 新增的 JavaScript 方法

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `getDeviceBindingType(row)` | 根据绑定情况返回标签颜色 | row: 卡密对象 |
| `handleViewDevices(row)` | 打开设备详情对话框 | row: 卡密对象 |
| `handleUnbindDevice(device)` | 解绑指定设备 | device: 设备对象 |
| `handleEditMaxDevices()` | 打开修改最大设备数对话框 | - |
| `handleUpdateMaxDevices()` | 提交更新最大设备数 | - |

---

## 🔍 常见问题

### Q1: 设备绑定数显示为 0/3，但用户说已经绑定了？

**可能原因**：
1. 客户端没有传递 `X-Device-ID` 请求头
2. 设备ID生成失败
3. 数据库中 `device_bindings` 表没有记录

**解决方案**：
1. 检查客户端代码是否正确传递设备ID
2. 查看数据库中的 `device_bindings` 表
3. 检查后端日志

---

### Q2: 修改最大设备数后，已绑定的设备会被自动解绑吗？

**答案**：不会。

- 如果当前绑定数为 3，修改最大设备数为 2，已绑定的 3 台设备仍然有效
- 但新设备无法绑定，直到解绑一台设备使绑定数降到 2 以下

---

### Q3: 设备ID是如何生成的？

**答案**：设备ID通过机器码（MachineId）生成，基于硬件信息：
- CPU ID
- 主板序列号
- MAC 地址
- 硬盘序列号

**注意**：
- 重装系统可能导致设备ID变化
- 虚拟机的设备ID可能不稳定

---

### Q4: 如何批量解绑所有设备？

**方法 1**：通过管理界面逐个解绑

**方法 2**：直接操作数据库（谨慎使用）
```sql
-- 解绑指定卡密的所有设备
UPDATE device_bindings 
SET is_active = false 
WHERE key_code = 'ABC123';

-- 解绑所有卡密的所有设备
UPDATE device_bindings 
SET is_active = false;
```

---

## 📝 部署检查清单

在使用设备绑定管理功能前，请确保：

- [x] 已运行数据库迁移脚本，添加 `max_devices` 字段
- [x] 已导入 `DeviceBinding` 模型到 `admin.py`
- [x] 已更新前端 `keys.html` 文件
- [x] 已重启后端服务
- [x] 已清除浏览器缓存

---

## 🎨 界面预览

### 卡密列表 - 设备绑定列

```
┌──────────────┬────────┬──────────┐
│ 卡密代码     │ 状态   │ 设备绑定 │
├──────────────┼────────┼──────────┤
│ ABC123...    │ 已激活 │ 2/3 详情 │
│ DEF456...    │ 已激活 │ 3/3 详情 │ ← 已达上限（红色）
│ GHI789...    │ 未激活 │ 0/3 详情 │
└──────────────┴────────┴──────────┘
```

### 设备绑定详情对话框

```
┌─────────────────────────────────────────┐
│  设备绑定详情                            │
├─────────────────────────────────────────┤
│  卡密：ABC123  |  已绑定：2/3 台设备    │
│  [修改最大设备数]                        │
├─────────────────────────────────────────┤
│  设备名称      │ 设备ID  │ 首次绑定     │
│  DESKTOP-PC   │ abc...  │ 2024-01-01  │
│  LAPTOP-HOME  │ def...  │ 2024-01-10  │
└─────────────────────────────────────────┘
```

---

## 🔐 安全建议

1. **定期检查异常绑定**：
   - 监控频繁绑定/解绑的卡密
   - 检查同一卡密绑定多个设备的情况

2. **设置合理的设备数上限**：
   - 个人用户：1-2台
   - 团队用户：3-5台
   - 企业用户：5-10台

3. **记录操作日志**：
   - 记录管理员的解绑操作
   - 记录设备绑定/解绑时间

---

## 📚 相关文件

| 文件路径 | 说明 |
|---------|------|
| `app/routers/admin.py` | 后端API（已添加设备绑定管理接口） |
| `app/models.py` | 数据库模型（DeviceBinding） |
| `app/templates/keys.html` | 前端页面（已添加设备绑定展示） |
| `fix_max_devices_column.sql` | 数据库迁移脚本 |
| `add_max_devices_migration.py` | Python迁移脚本 |

---

## ✅ 总结

设备绑定管理功能已完整集成到后端管理系统，提供了：

1. **可视化展示**：在卡密列表中直观显示设备绑定情况
2. **详细信息**：查看每个设备的绑定时间、活跃时间、请求次数
3. **灵活管理**：支持修改最大设备数、强制解绑设备
4. **颜色标识**：通过颜色快速识别绑定状态

管理员可以轻松监控和管理所有卡密的设备绑定情况，有效防止卡密滥用。
