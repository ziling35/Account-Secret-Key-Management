# 设备绑定功能说明

## 📋 功能概述

为卡密系统添加设备绑定限制功能，每个卡密可以限制绑定的设备数量，防止卡密被多人共享使用。

## 🎯 核心特性

### 1. 设备绑定限制
- 每个卡密可设置最大设备绑定数（默认1台）
- 设备通过唯一ID（机器码）进行识别
- 超过限制时拒绝新设备访问

### 2. 设备管理
- 查看已绑定的设备列表
- 查看设备绑定时间和活跃时间
- 支持手动解绑设备
- 显示每个设备的请求次数

### 3. 自动绑定
- 首次使用时自动绑定当前设备
- 已绑定设备自动更新活跃时间
- 设备信息包含设备名称（可选）

## 🔧 实现细节

### 数据库变更

#### 1. Keys 表新增字段
```sql
ALTER TABLE keys 
ADD COLUMN max_devices INTEGER NOT NULL DEFAULT 1;
```

#### 2. 新增 device_bindings 表
```sql
CREATE TABLE device_bindings (
    id SERIAL PRIMARY KEY,
    key_code VARCHAR NOT NULL,
    device_id VARCHAR NOT NULL,
    device_name VARCHAR,
    first_bound_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    request_count INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX ix_device_bindings_key_code ON device_bindings(key_code);
CREATE INDEX ix_device_bindings_device_id ON device_bindings(device_id);
```

### API 接口

#### 1. 获取账号接口（修改）
**请求头新增：**
- `X-Device-ID`: 设备唯一标识（必需）
- `X-Device-Name`: 设备名称（可选）

**逻辑：**
1. 验证卡密有效性
2. 检查设备是否已绑定
3. 如未绑定，检查是否超过最大绑定数
4. 自动绑定新设备或更新已绑定设备的活跃时间

**错误响应：**
```json
{
  "detail": "设备绑定数已达上限（1台），请先解绑其他设备"
}
```

#### 2. 查询设备绑定列表
```
GET /api/client/device/list
Headers: X-API-Key: <your-key>
```

**响应：**
```json
{
  "success": true,
  "message": "获取成功，共 2 台设备",
  "devices": [
    {
      "id": 1,
      "device_id": "abc123...",
      "device_name": "DESKTOP-PC",
      "first_bound_at": "2024-01-01T10:00:00",
      "last_active_at": "2024-01-15T15:30:00",
      "request_count": 150,
      "is_active": true
    }
  ],
  "total": 2,
  "max_devices": 3
}
```

#### 3. 解绑设备
```
POST /api/client/device/unbind
Headers: X-API-Key: <your-key>
Body: {
  "device_id": "abc123..."
}
```

**响应：**
```json
{
  "success": true,
  "message": "设备解绑成功"
}
```

### 客户端集成

#### 1. KeyManager 更新

**新增方法：**
```javascript
// 获取账号（支持设备ID）
async getAccount(deviceId = null, deviceName = null)

// 获取设备绑定列表
async getDeviceBindings()

// 解绑设备
async unbindDevice(deviceId)
```

**使用示例：**
```javascript
const DeviceManager = require('./modules/deviceManager');
const KeyManager = require('./modules/keyManager');

// 获取设备ID
const deviceManager = new DeviceManager();
const deviceIds = deviceManager.getCurrentDeviceIds();
const deviceId = deviceIds?.machineId || 'unknown';
const deviceName = require('os').hostname();

// 获取账号时传入设备ID
const keyManager = new KeyManager(appDataPath);
const result = await keyManager.getAccount(deviceId, deviceName);

if (!result.success) {
  if (result.message.includes('设备绑定数已达上限')) {
    // 提示用户解绑其他设备
    console.log('设备绑定已满，请在设置中解绑其他设备');
  }
}
```

#### 2. 设备管理界面

**功能：**
- 显示已绑定设备列表
- 显示设备绑定时间和最后活跃时间
- 提供解绑按钮
- 显示当前设备标识

### 插件集成

插件在验证卡密时也需要传递设备ID：

```typescript
// 在插件的API请求中添加设备ID
const headers = {
  'X-API-Key': apiKey,
  'X-Device-ID': getDeviceId(),  // 获取设备唯一标识
  'X-Device-Name': os.hostname()
};
```

## 📝 使用流程

### 管理员操作

1. **创建卡密时设置设备绑定数**
   - 在管理后台创建卡密
   - 设置 `max_devices` 字段（默认1）
   - 例如：单人卡密设为1，团队卡密可设为3-5

2. **查看设备绑定情况**
   - 在管理后台查看每个卡密的设备绑定
   - 可以强制解绑设备（如需要）

### 用户操作

1. **首次使用**
   - 输入卡密激活
   - 自动绑定当前设备
   - 正常使用

2. **更换设备**
   - 在新设备上使用卡密
   - 如超过绑定数限制，会提示解绑
   - 在客户端设置中解绑旧设备
   - 重新获取账号，自动绑定新设备

3. **管理设备**
   - 打开客户端设置
   - 查看"设备绑定管理"
   - 查看已绑定设备列表
   - 解绑不再使用的设备

## 🔒 安全考虑

1. **设备ID获取**
   - 使用机器码（MachineId）作为设备唯一标识
   - 基于硬件信息生成，不易伪造
   - 重装系统会改变设备ID

2. **防滥用措施**
   - 记录设备绑定时间和活跃时间
   - 记录每个设备的请求次数
   - 管理员可查看异常绑定行为

3. **解绑限制**
   - 用户可自行解绑设备
   - 建议添加解绑冷却时间（可选）
   - 管理员可强制解绑

## 🚀 部署步骤

### 1. 数据库迁移
```bash
cd Account-Secret-Key-Management
python migrate_device_binding.py
```

### 2. 更新后端代码
- 已更新 `models.py`（添加DeviceBinding模型）
- 已更新 `schemas.py`（添加设备绑定Schema）
- 已更新 `routers/client.py`（添加设备绑定接口）

### 3. 更新客户端代码
- 已更新 `modules/keyManager.js`（添加设备绑定方法）
- 需要更新 `renderer/renderer.js`（添加UI交互）
- 需要更新 `main.js`（集成设备ID获取）

### 4. 更新插件代码
- 需要在插件中添加设备ID传递逻辑

## 📊 监控建议

1. **设备绑定统计**
   - 统计平均每个卡密绑定设备数
   - 识别异常绑定行为（频繁绑定/解绑）

2. **设备活跃度**
   - 监控设备最后活跃时间
   - 清理长期不活跃的绑定

3. **错误监控**
   - 记录设备绑定失败次数
   - 分析失败原因

## 🎨 UI 设计建议

### 设备管理页面
```
┌─────────────────────────────────────┐
│  设备绑定管理                        │
├─────────────────────────────────────┤
│  当前设备: DESKTOP-PC (abc123...)   │
│  已绑定: 1/3 台设备                 │
├─────────────────────────────────────┤
│  设备列表:                          │
│  ┌───────────────────────────────┐ │
│  │ 🖥️ DESKTOP-PC (当前设备)      │ │
│  │ 首次绑定: 2024-01-01          │ │
│  │ 最后活跃: 刚刚                │ │
│  │ 请求次数: 150                 │ │
│  └───────────────────────────────┘ │
│  ┌───────────────────────────────┐ │
│  │ 💻 LAPTOP-HOME                │ │
│  │ 首次绑定: 2024-01-10          │ │
│  │ 最后活跃: 3天前               │ │
│  │ 请求次数: 45                  │ │
│  │ [解绑设备]                    │ │
│  └───────────────────────────────┘ │
└─────────────────────────────────────┘
```

## ⚠️ 注意事项

1. **设备ID变化**
   - 重装系统会导致设备ID变化
   - 需要重新绑定（解绑旧设备）

2. **虚拟机使用**
   - 虚拟机的设备ID可能不稳定
   - 建议提示用户使用物理机

3. **向后兼容**
   - 旧客户端不传设备ID时，不进行绑定限制
   - 建议强制更新客户端

## 📚 相关文件

- `app/models.py` - 数据库模型
- `app/schemas.py` - API Schema
- `app/routers/client.py` - 客户端API
- `modules/keyManager.js` - 客户端密钥管理
- `modules/deviceManager.js` - 设备管理
- `migrate_device_binding.py` - 数据库迁移脚本
