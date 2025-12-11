# 模板语法冲突修复

## 问题描述

访问公告管理页面时报错：
```
jinja2.exceptions.TemplateSyntaxError: unexpected char '?' at 1450
```

## 原因分析

在 `announcements.html` 模板中，Vue 3 和 Jinja2 都使用了 `{{ }}` 作为模板分隔符，导致语法冲突。

Jinja2 在服务器端渲染时会尝试解析 Vue 的模板语法，遇到 JavaScript 的三元运算符 `?:` 时报错。

### 冲突示例

```html
<!-- Vue 模板语法 -->
<el-tag :type="scope.row.is_active ? 'success' : 'info'">
    {{ scope.row.is_active ? '启用' : '禁用' }}
</el-tag>

<!-- Jinja2 会尝试解析 {{ }} 中的内容 -->
<!-- 但 JavaScript 的 ? : 语法在 Jinja2 中不合法 -->
```

## 解决方案

修改 Vue 3 的模板分隔符从 `{{ }}` 改为 `[[ ]]`，避免与 Jinja2 冲突。

### 修改步骤

#### 1. 配置 Vue 应用的自定义分隔符

```javascript
createApp({
    delimiters: ['[[', ']]'],  // 添加这一行
    data() {
        return {
            // ...
        };
    },
    // ...
}).use(ElementPlus).mount('#app');
```

#### 2. 替换所有 Vue 模板中的分隔符

**修改前：**
```html
{{ scope.row.content.substring(0, 100) }}
{{ scope.row.is_active ? '启用' : '禁用' }}
{{ formatDate(scope.row.created_at) }}
{{ scope.row.created_by || '-' }}
{{ dialogMode === 'create' ? '创建' : '保存' }}
```

**修改后：**
```html
[[ scope.row.content.substring(0, 100) ]]
[[ scope.row.is_active ? '启用' : '禁用' ]]
[[ formatDate(scope.row.created_at) ]]
[[ scope.row.created_by || '-' ]]
[[ dialogMode === 'create' ? '创建' : '保存' ]]
```

## 修复的文件

- `app/templates/announcements.html`
  - 添加 `delimiters: ['[[', ']]']` 配置
  - 替换所有 `{{ }}` 为 `[[ ]]`

## 其他解决方案

### 方案 1：使用 Jinja2 的 raw 标签（不推荐）

```html
{% raw %}
<div>
    {{ vue_variable }}
</div>
{% endraw %}
```

**缺点**：需要包裹大量代码，不够优雅。

### 方案 2：修改 Jinja2 的分隔符（不推荐）

```python
templates = Jinja2Templates(
    directory="app/templates",
    variable_start_string='{$',
    variable_end_string='$}'
)
```

**缺点**：影响所有模板文件，需要大量修改。

### 方案 3：修改 Vue 的分隔符（推荐）✅

```javascript
createApp({
    delimiters: ['[[', ']]']
})
```

**优点**：
- 只需修改一个文件
- 不影响其他模板
- 代码清晰易懂
- 是 Vue 官方推荐的解决方案

## 注意事项

### 1. 其他模板文件检查

如果其他模板文件也使用了 Vue 3，需要进行相同的修改：
- `keys.html`
- `accounts.html`
- `settings.html`
- `dashboard.html`

### 2. 分隔符一致性

确保在同一个 Vue 应用中，所有模板使用相同的分隔符。

### 3. 文档说明

在项目文档中说明使用了自定义分隔符，方便其他开发者了解。

## 测试验证

### 1. 访问公告管理页面

```bash
http://localhost:8000/admin/announcements
```

应该能正常显示，不再报错。

### 2. 测试功能

- ✅ 创建公告
- ✅ 编辑公告
- ✅ 启用/禁用公告
- ✅ 删除公告
- ✅ 查看公告列表

### 3. 检查数据显示

- ✅ 公告内容正确显示
- ✅ 状态标签正确显示（启用/禁用）
- ✅ 创建时间正确格式化
- ✅ 创建人正确显示
- ✅ 按钮文字正确显示（创建/保存）

## 相关文档

- [Vue 3 官方文档 - 自定义分隔符](https://vuejs.org/api/application.html#app-config-compileroptions-delimiters)
- [Jinja2 官方文档 - 语法](https://jinja.palletsprojects.com/en/3.1.x/templates/)

## 总结

通过修改 Vue 3 的模板分隔符，成功解决了与 Jinja2 的语法冲突问题。这是一个常见的问题，在使用服务器端模板引擎和前端框架时经常遇到。

---

**修复日期**: 2024-12-09  
**状态**: ✅ 已修复  
**影响文件**: `app/templates/announcements.html`
