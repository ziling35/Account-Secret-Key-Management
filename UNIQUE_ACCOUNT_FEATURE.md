# 账号去重功能说明

## 功能概述

当客户端使用同一个密钥多次请求获取账号时，系统会自动排除该密钥之前获取过的账号，确保每次获取到的都是**新的、不同的账号**。

## 工作原理

### 1. 账号分配逻辑

```
客户端请求获取账号（使用密钥 A）
    ↓
查询密钥 A 之前获取过的所有账号
    ↓
从未使用账号中排除这些已获取过的账号
    ↓
分配一个新的账号给密钥 A
    ↓
记录该账号已被密钥 A 获取
```

### 2. 数据库查询

系统会执行以下查询：

```sql
-- 1. 查询该密钥之前获取过的账号
SELECT email FROM accounts 
WHERE assigned_to_key = 'your_key_code';

-- 2. 获取未使用的账号，排除之前获取过的
SELECT * FROM accounts 
WHERE status = 'unused' 
  AND email NOT IN (之前获取过的邮箱列表)
ORDER BY created_at ASC 
LIMIT 1;
```

## 使用场景

### 场景 1：用户切换账号

**需求：**
- 用户使用密钥 A 获取了账号 1
- 用户想切换到新账号
- 再次使用密钥 A 请求

**系统行为：**
- ✅ 自动排除账号 1
- ✅ 分配账号 2（新账号）
- ✅ 记录账号 2 已被密钥 A 获取

**示例：**
```bash
# 第一次请求
curl -X POST "http://localhost:8000/api/client/account/get" \
  -H "X-API-Key: key123"
# 返回: user1@example.com

# 第二次请求（同一个密钥）
curl -X POST "http://localhost:8000/api/client/account/get" \
  -H "X-API-Key: key123"
# 返回: user2@example.com （不会返回 user1）

# 第三次请求
curl -X POST "http://localhost:8000/api/client/account/get" \
  -H "X-API-Key: key123"
# 返回: user3@example.com （不会返回 user1 或 user2）
```

### 场景 2：多次获取

**需求：**
- 用户需要多个不同的账号
- 使用同一个密钥多次请求

**系统行为：**
- ✅ 每次都返回新账号
- ✅ 不会重复分配
- ✅ 按创建时间顺序分配

**示例：**
```python
import requests

api_key = "key123"
accounts = []

# 获取 5 个不同的账号
for i in range(5):
    response = requests.post(
        "http://localhost:8000/api/client/account/get",
        headers={"X-API-Key": api_key}
    )
    account = response.json()
    accounts.append(account['email'])
    print(f"第 {i+1} 次获取: {account['email']}")

# 输出：
# 第 1 次获取: user1@example.com
# 第 2 次获取: user2@example.com
# 第 3 次获取: user3@example.com
# 第 4 次获取: user4@example.com
# 第 5 次获取: user5@example.com

# 所有账号都不相同
print(f"获取到 {len(set(accounts))} 个不同账号")  # 输出: 5
```

### 场景 3：账号用完提示

**需求：**
- 所有未使用账号都已被该密钥获取过
- 用户再次请求

**系统行为：**
- ⚠️ 返回明确的错误提示
- 📝 区分"无可用账号"和"无新账号"

**示例：**
```bash
# 假设只有 3 个账号，密钥已获取过所有账号
curl -X POST "http://localhost:8000/api/client/account/get" \
  -H "X-API-Key: key123"

# 返回错误：
{
  "detail": "暂无新账号可用（所有未使用账号都已被该密钥获取过）"
}
```

## 技术实现

### 数据库字段

使用 `accounts.assigned_to_key` 字段记录账号被哪个密钥获取：

```python
class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    api_key = Column(String, nullable=True)
    name = Column(String, nullable=True)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.unused)
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime, nullable=True)
    assigned_to_key = Column(String, nullable=True)  # 记录分配给哪个密钥
```

### 核心代码

```python
# 1. 查询该密钥之前获取过的账号
previously_assigned_emails = db.query(Account.email).filter(
    Account.assigned_to_key == api_key
).all()
previously_assigned_emails = [email[0] for email in previously_assigned_emails]

# 2. 获取未使用的账号，排除之前获取过的
query = db.query(Account).filter(
    Account.status == AccountStatus.unused
)

if previously_assigned_emails:
    query = query.filter(Account.email.notin_(previously_assigned_emails))

account = query.order_by(Account.created_at.asc()).first()

# 3. 检查是否有可用账号
if not account:
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
```

## 优势

### 1. 避免重复
- ✅ 同一密钥不会获取到相同账号
- ✅ 用户切换账号时自动获取新账号
- ✅ 提升用户体验

### 2. 公平分配
- ✅ 按创建时间顺序分配
- ✅ 确保所有账号都能被使用
- ✅ 避免某些账号被重复使用

### 3. 明确提示
- ✅ 区分"无账号"和"无新账号"
- ✅ 帮助用户了解系统状态
- ✅ 便于问题排查

## 注意事项

### 1. 账号池大小

**建议：**
- 确保账号池足够大
- 监控账号使用情况
- 及时补充新账号

**示例：**
```
密钥类型：有限额度（10 次）
账号池大小：至少 10 个账号
原因：确保每次都能获取到新账号
```

### 2. 状态管理

**重要：**
- 账号状态从 `unused` 变为 `used` 后不会再被分配
- 如果需要重复使用账号，需要手动重置状态

**重置账号状态：**
```bash
# 通过管理后台重置账号状态为 unused
curl -X POST "http://localhost:8000/admin/api/accounts/update-status/{account_id}" \
  -H "Cookie: admin_session=your_session" \
  -d "status=unused"
```

### 3. 密钥类型影响

#### 无限额度密钥
- 可以无限次获取账号
- 每次都会获取新账号
- 直到所有账号都被获取过

#### 有限额度密钥
- 受账号配额限制
- 每次获取计入配额
- 配额用完后无法再获取

## 测试示例

### 测试脚本

```python
import requests
import time

API_URL = "http://localhost:8000/api/client/account/get"
API_KEY = "your_key_code"

def test_unique_accounts():
    """测试账号去重功能"""
    print("=" * 60)
    print("测试账号去重功能")
    print("=" * 60)
    
    accounts = []
    
    # 连续获取 5 个账号
    for i in range(5):
        try:
            response = requests.post(
                API_URL,
                headers={"X-API-Key": API_KEY}
            )
            
            if response.status_code == 200:
                data = response.json()
                email = data['email']
                accounts.append(email)
                print(f"\n第 {i+1} 次获取:")
                print(f"  邮箱: {email}")
                print(f"  API Key: {data['api_key'][:20]}...")
                
                # 检查是否重复
                if accounts.count(email) > 1:
                    print(f"  ⚠️  警告: 获取到重复账号！")
                else:
                    print(f"  ✅ 新账号")
            else:
                print(f"\n第 {i+1} 次获取失败:")
                print(f"  错误: {response.json()['detail']}")
                break
            
            # 等待一段时间（如果是无限额度密钥）
            if i < 4:
                print("\n等待 5 分钟后继续...")
                time.sleep(300)  # 5 分钟
                
        except Exception as e:
            print(f"\n第 {i+1} 次获取异常: {str(e)}")
            break
    
    # 统计结果
    print("\n" + "=" * 60)
    print("测试结果:")
    print("=" * 60)
    print(f"总共获取: {len(accounts)} 个账号")
    print(f"不同账号: {len(set(accounts))} 个")
    print(f"重复账号: {len(accounts) - len(set(accounts))} 个")
    
    if len(accounts) == len(set(accounts)):
        print("\n✅ 测试通过：所有账号都不相同")
    else:
        print("\n❌ 测试失败：存在重复账号")
        print(f"重复的账号: {[a for a in accounts if accounts.count(a) > 1]}")

if __name__ == "__main__":
    test_unique_accounts()
```

### 预期输出

```
============================================================
测试账号去重功能
============================================================

第 1 次获取:
  邮箱: user1@example.com
  API Key: sk-ws-01-xxxxxxxxxx...
  ✅ 新账号

等待 5 分钟后继续...

第 2 次获取:
  邮箱: user2@example.com
  API Key: sk-ws-01-yyyyyyyyyy...
  ✅ 新账号

等待 5 分钟后继续...

第 3 次获取:
  邮箱: user3@example.com
  API Key: sk-ws-01-zzzzzzzzzz...
  ✅ 新账号

============================================================
测试结果:
============================================================
总共获取: 3 个账号
不同账号: 3 个
重复账号: 0 个

✅ 测试通过：所有账号都不相同
```

## 常见问题

### Q1: 为什么还是获取到了相同的账号？

**可能原因：**
1. 账号状态被重置为 `unused`
2. 使用了不同的密钥
3. 数据库记录被清除

**解决方案：**
- 检查账号状态
- 确认使用的密钥
- 查看 `assigned_to_key` 字段

### Q2: 如何重置密钥的获取记录？

**方法 1：重置所有账号状态**
```sql
UPDATE accounts 
SET status = 'unused', 
    assigned_to_key = NULL, 
    assigned_at = NULL 
WHERE assigned_to_key = 'your_key_code';
```

**方法 2：通过管理后台逐个重置**
- 进入账号管理页面
- 找到该密钥获取的账号
- 修改状态为 `unused`

### Q3: 账号用完了怎么办？

**解决方案：**
1. 上传新的账号文件
2. 重置已使用账号的状态
3. 使用新的密钥

## 相关文档

- [API Key 可选功能](OPTIONAL_API_KEY.md)
- [登录功能说明](LOGIN_FEATURE.md)
- [更新日志](CHANGELOG.md)

---

**版本**: v1.2.0  
**日期**: 2024-12-09  
**状态**: ✅ 已实现
