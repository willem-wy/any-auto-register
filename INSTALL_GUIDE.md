# 即梦平台插件安装指南

##  当前状态

✅ **插件代码已完成并通过结构验证**
- 所有文件已创建
- Python 语法正确
- 关键类和函数已定义
- 插件注册装饰器已添加
- 正确继承 BasePlatform

## ⚠️ 环境问题

当前系统的 Python 版本为 **3.8.2**，但项目需要 **Python 3.11+**。

### 问题详情
- 系统 Python 3.8 缺少 macOS SDK
- 无法创建虚拟环境
- 无法安装 playwright（需要 Python 3.9+）

##  解决方案

### 方案 A：安装 Python 3.11（推荐）

#### 1. 使用 Homebrew 安装
```bash
# 安装 Homebrew（如果未安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Python 3.11
brew install python@3.11

# 验证安装
python3.11 --version
```

#### 2. 创建虚拟环境
```bash
cd /Users/admin/Desktop/myapps/any-auto-register
python3.11 -m venv .venv
source .venv/bin/activate
```

#### 3. 安装依赖
```bash
# 升级 pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
python -m playwright install chromium
```

#### 4. 运行测试
```bash
# 结构验证测试
python test_plugin_structure.py

# 完整功能测试
python test_jimeng_plugin.py
```

#### 5. 启动服务
```bash
python -m uvicorn main:app --port 8000
```

### 方案 B：使用 pyenv 管理多版本 Python

#### 1. 安装 pyenv
```bash
brew install pyenv
```

#### 2. 配置 shell
```bash
# 添加到 ~/.zshrc 或 ~/.bash_profile
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
```

#### 3. 安装 Python 3.11
```bash
pyenv install 3.11.7
pyenv global 3.11.7
```

#### 4. 继续安装流程
```bash
cd /Users/admin/Desktop/myapps/any-auto-register
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 方案 C：使用 Docker（最简单）

如果不想处理 Python 环境问题，可以使用 Docker：

```bash
cd /Users/admin/Desktop/myapps/any-auto-register

# 构建镜像
docker build -t any-auto-register .

# 运行容器
docker run -d \
  --name any-auto-register \
  -p 8000:8000 \
  -p 6080:6080 \
  -p 8889:8889 \
  -v $(pwd)/data:/app/data \
  -e DISPLAY=:99 \
  any-auto-register
```

访问：
- Web UI: http://localhost:8000
- noVNC: http://localhost:6080/vnc.html
- Solver: http://localhost:8889

##  验证安装

### 1. 检查 Python 版本
```bash
python --version
# 应该显示 Python 3.11.x
```

### 2. 检查依赖
```bash
pip list | grep -E "sqlmodel|playwright|fastapi"
```

### 3. 运行结构测试
```bash
python test_plugin_structure.py
```

应该看到所有检查项都显示 ✅

### 4. 运行完整测试
```bash
python test_jimeng_plugin.py
```

应该看到：
```
✅ 即梦平台已注册：即梦 AI
   版本：1.0.0
   支持的执行器：['headless', 'headed']
   支持的身份模式：['mailbox']
   平台能力：['query_state', 'check_valid']
```

### 5. 启动服务并访问 UI
```bash
python -m uvicorn main:app --port 8000
```

打开浏览器访问 http://localhost:8000，应该能在平台列表中看到"即梦 AI"。

##  常见问题

### Q1: brew install python@3.11 失败
**A**: 尝试更新 Homebrew 或使用其他版本：
```bash
brew update
brew install python@3.12
```

### Q2: playwright install chromium 失败
**A**: 可能需要安装依赖：
```bash
# macOS
playwright install-deps

# 或者手动安装
brew install n
```

### Q3: 端口 8000 被占用
**A**: 使用其他端口：
```bash
python -m uvicorn main:app --port 8001
```

### Q4: 数据库文件不存在
**A**: 首次运行时会自动创建：
```bash
mkdir -p data
```

##  下一步

安装完成后：

1. **准备测试邮箱**
   - 推荐使用 MoeMail（自建临时邮箱）
   - 或 Testmail（testmail.app）

2. **配置邮箱服务**
   - 在 Web UI 的"全局配置"中添加邮箱服务
   - 填写必要的 API 密钥

3. **创建注册任务**
   - 选择"即梦 AI"平台
   - 选择执行器类型（headless 或 headed）
   - 填写邮箱地址
   - 开始注册

4. **同步到账号池**
   ```bash
   python tools/jimeng_pool_sync.py
   ```

##  技术支持

如果遇到问题：

1. 查看日志文件
2. 检查浏览器截图（`/tmp/jimeng_*.png`）
3. 参考 `platforms/jimeng/README.md`
4. 查看 Any Auto Register 官方文档

##  总结

当前插件代码已完成，只需要：
1. ✅ 安装 Python 3.11+
2. ✅ 创建虚拟环境
3. ✅ 安装依赖
4. ✅ 安装 Playwright 浏览器
5. ✅ 运行测试

预计安装时间：**10-15 分钟**
