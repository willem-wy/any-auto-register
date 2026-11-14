# 即梦 AI 平台插件

## 功能特性

- ✅ 浏览器自动化注册（Headless/Headed 模式）
- ✅ 自动提取 Session Cookie
- ✅ 账号有效性检测
- ✅ 积分余额查询
- ✅ 支持邮箱验证码注册

## 安装步骤

### 1. 安装依赖

```bash
cd /Users/admin/Desktop/myapps/any-auto-register
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 安装 Playwright 浏览器

```bash
python3 -m playwright install chromium
```

### 3. 验证插件加载

```bash
python3 test_jimeng_plugin.py
```

应该看到输出：
```
✅ 即梦平台已注册：即梦 AI
   版本：1.0.0
   支持的执行器：['headless', 'headed']
   支持的身份模式：['mailbox']
   平台能力：['query_state', 'check_valid']
```

## 使用方法

### 通过 Web UI

1. 启动服务：
```bash
python3 -m uvicorn main:app --port 8000
```

2. 访问 `http://localhost:8000`

3. 在平台列表中选择"即梦 AI"

4. 配置邮箱服务（推荐使用 MoeMail 或 Testmail）

5. 创建注册任务

### 通过 API

```bash
# 创建注册任务
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "jimeng",
    "executor_type": "headless",
    "identity": {
      "identity_provider": "mailbox",
      "email": "your-email@example.com"
    }
  }'

# 查询账号状态
curl -X POST http://localhost:8000/api/actions/execute \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "jimeng",
    "action_id": "check_account",
    "account": {
      "platform": "jimeng",
      "token": "your-session-id"
    }
  }'
```

## 注册流程说明

即梦使用字节跳动的统一登录体系（Passport），注册流程如下：

1. **打开登录页** - 访问 `jimeng.jianying.com/ai-tool/login`
2. **选择登录方式** - 切换到密码登录模式
3. **输入账号密码** - 填写邮箱和密码
4. **获取验证码** - 通过邮箱接收验证码
5. **完成登录** - 提交验证码完成注册
6. **提取 Cookie** - 自动提取 `sessionid` 和 `sessionid_ss`
7. **保存账号** - 将 Cookie 保存到账号池

## 注意事项

### 反检测措施

插件已内置以下反检测措施：
- 隐藏 WebDriver 特征
- 模拟真实浏览器环境
- 设置中文语言和时区
- 使用真实 User-Agent

### Cookie 有效期

- 即梦 Cookie 通常有效期为 **7-30 天**
- 建议定期检测账号有效性
- 失效后需要重新注册

### 验证码处理

- 支持自动验证码填充（需配置验证码服务）
- 支持手动输入验证码（Headed 模式）
- 推荐使用 2Captcha 或 YesCaptcha

### 代理支持

- 支持 HTTP/HTTPS 代理
- 建议在注册时使用代理避免 IP 封禁
- 可在任务配置中设置代理

## 故障排查

### 问题 1：登录失败

**症状**：提示"未找到 sessionid Cookie"

**解决方案**：
1. 检查邮箱是否正确
2. 检查验证码是否及时输入
3. 查看截图 `/tmp/jimeng_login_failed.png`
4. 尝试使用 Headed 模式手动完成

### 问题 2：验证码超时

**症状**：等待验证码超时

**解决方案**：
1. 检查邮箱服务配置
2. 增加验证码等待时间
3. 更换邮箱服务提供商

### 问题 3：账号检测失败

**症状**：`check_valid` 返回 False

**解决方案**：
1. 检查 session_id 是否正确
2. 检查 Cookie 是否过期
3. 尝试刷新 Cookie

## 开发说明

### 文件结构

```
platforms/jimeng/
├── __init__.py          # 模块初始化
├── core.py              # 常量配置
├── browser_register.py  # 浏览器注册流程
└── plugin.py            # 平台插件定义
```

### 扩展功能

如需添加新功能，可以：

1. **添加新的操作** - 在 `plugin.py` 的 `get_platform_actions()` 中添加
2. **优化注册流程** - 修改 `browser_register.py` 中的 `run()` 方法
3. **添加协议模式** - 实现 `build_protocol_mailbox_adapter()`

### 调试技巧

```python
# 在 browser_register.py 中添加日志
self.log(f"调试信息：{variable}")

# 保存截图
await page.screenshot(path="/tmp/debug.png")

# 获取页面内容
content = await page.content()
print(content)
```

## 许可证

与 Any Auto Register 主项目保持一致。
