# 即梦平台插件开发完成

## 已完成的工作

### 1. 插件文件结构
```
platforms/jimeng/
├── __init__.py          # 模块初始化
├── core.py              # 常量配置（域名、API 端点、Cookie 字段）
├── browser_register.py  # 浏览器自动化注册流程
├── plugin.py            # 平台插件定义（继承 BasePlatform）
└── README.md            # 使用说明文档
```

### 2. 核心功能

#### ✅ 浏览器自动化注册
- 使用 Playwright 启动 Chromium 浏览器
- 自动打开即梦登录页
- 自动填写邮箱和密码
- 自动勾选用户协议
- 支持验证码处理（自动/手动）
- 自动提取 sessionid Cookie

#### ✅ 反检测措施
- 隐藏 WebDriver 特征
- 模拟真实浏览器环境
- 设置中文语言和时区（Asia/Shanghai）
- 使用真实 User-Agent

#### ✅ 账号管理
- 账号有效性检测（check_valid）
- 积分余额查询（get_account_status）
- 支持平台操作（get_platform_actions）

#### ✅ 账号池集成
- 提供 `tools/jimeng_pool_sync.py` 脚本
- 自动同步到 jimeng-free-api-all 的账号池数据库
- 支持创建、查询、删除账号

### 3. 技术实现

#### 注册流程
1. 启动 Playwright Chromium 浏览器
2. 访问 `jimeng.jianying.com/ai-tool/login`
3. 点击登录按钮，打开登录弹窗
4. 切换到密码登录模式
5. 输入邮箱和密码
6. 勾选用户协议
7. 提交登录
8. 处理验证码（等待回调）
9. 等待登录成功（URL 变化或用户头像出现）
10. 提取 sessionid 和 sessionid_ss Cookie
11. 获取用户信息
12. 返回注册结果

#### Cookie 提取
- 主 Cookie：`sessionid`
- 备用 Cookie：`sessionid_ss`
- 完整 Cookie 字典（用于后续请求）

### 4. 使用方式

#### 方式 A：通过 Web UI
1. 启动 any-auto-register 服务
2. 访问 `http://localhost:8000`
3. 选择"即梦 AI"平台
4. 配置邮箱服务
5. 创建注册任务

#### 方式 B：通过 API
```bash
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
```

#### 方式 C：同步到账号池
```bash
cd /Users/admin/Desktop/myapps/any-auto-register
python3 tools/jimeng_pool_sync.py
```

### 5. 下一步

#### 需要完成的工作
1. **安装依赖**
   ```bash
   cd /Users/admin/Desktop/myapps/any-auto-register
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python3 -m playwright install chromium
   ```

2. **测试插件加载**
   ```bash
   python3 test_jimeng_plugin.py
   ```

3. **实际注册测试**
   - 准备一个测试邮箱
   - 创建注册任务
   - 验证 Cookie 提取
   - 同步到账号池

#### 可选优化
1. **验证码自动填充** - 集成 2Captcha/YesCaptcha
2. **Cookie 自动续期** - 定期刷新 sessionid
3. **多账号并发** - 支持批量注册
4. **失败重试** - 自动处理临时错误

### 6. 注意事项

⚠️ **重要提示**：
- 即梦使用字节 Passport 登录体系，需要手机/邮箱验证码
- Cookie 有效期约 7-30 天，需要定期检测
- 建议使用代理避免 IP 封禁
- 遵守即梦服务条款，仅用于学习研究

### 7. 文件清单

```
/Users/admin/Desktop/myapps/any-auto-register/
├── platforms/jimeng/
│   ├── __init__.py          (103 bytes)
│   ├── core.py              (778 bytes)
│   ├── browser_register.py  (9.3 KB)
│   ├── plugin.py            (6.5 KB)
│   └── README.md            (完整文档)
├── tools/jimeng_pool_sync.py  (账号池集成脚本)
└── test_jimeng_plugin.py      (插件测试脚本)
```

## 总结

✅ 已完成即梦平台插件的完整开发
✅ 支持浏览器自动化注册
✅ 支持账号有效性检测
✅ 提供账号池集成工具
✅ 包含完整的使用文档

现在你可以：
1. 安装依赖并测试插件
2. 准备测试邮箱进行实际注册
3. 将注册的账号同步到 jimeng-free-api-all 账号池

需要我帮你测试或调整任何功能吗？
