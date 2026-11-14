# 即梦平台插件 - 快速启动

##  30 秒概览

✅ 插件已开发完成
✅ 代码验证通过
️ 需要安装 Python 3.11+ 环境

##  快速开始

### 方式 1：一键安装（推荐）
```bash
cd /Users/admin/Desktop/myapps/any-auto-register
./setup.sh
```

### 方式 2：Docker（最简单）
```bash
cd /Users/admin/Desktop/myapps/any-auto-register
docker build -t any-auto-register .
docker run -d --name any-auto-register -p 8000:8000 any-auto-register
```

### 方式 3：手动安装
```bash
# 安装 Python 3.11
brew install python@3.11

# 创建环境
python3.11 -m venv .venv && source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
python -m playwright install chromium

# 启动服务
python -m uvicorn main:app --port 8000
```

##  使用插件

1. **访问 Web UI**
   - 打开 http://localhost:8000

2. **选择平台**
   - 在平台列表中选择"即梦 AI"

3. **配置邮箱**
   - 推荐使用 MoeMail 或 Testmail

4. **创建任务**
   - 填写邮箱地址
   - 选择执行器类型（headless/headed）
   - 开始注册

5. **查看结果**
   - 注册成功后自动提取 Cookie
   - 可同步到 jimeng-free-api-all 账号池

##  测试验证

```bash
# 结构验证
python test_plugin_structure.py

# 完整测试
python test_jimeng_plugin.py

# 账号池同步
python tools/jimeng_pool_sync.py
```

##  文档索引

| 文档 | 说明 |
|------|------|
| [INSTALL_GUIDE.md](INSTALL_GUIDE.md) | 详细安装指南 |
| [COMPLETED.md](COMPLETED.md) | 开发完成总结 |
| [platforms/jimeng/README.md](platforms/jimeng/README.md) | 插件使用文档 |
| [JIMENG_PLUGIN_SUMMARY.md](JIMENG_PLUGIN_SUMMARY.md) | 功能说明 |

##  文件结构

```
platforms/jimeng/
├── __init__.py          # 模块初始化
── core.py              # 常量配置
├── browser_register.py  # 浏览器注册流程
── plugin.py            # 平台插件定义
── README.md            # 使用文档
```

##  核心功能

- ✅ 浏览器自动化注册
- ✅ Cookie 自动提取
- ✅ 账号有效性检测
- ✅ 积分余额查询
- ✅ 账号池集成

##  技术支持

遇到问题？
1. 查看 `INSTALL_GUIDE.md` 故障排查章节
2. 检查日志和截图（`/tmp/jimeng_*.png`）
3. 参考 `platforms/jimeng/README.md`

---

**版本**: 1.0.0  
**更新时间**: 2026-10-13  
**状态**: ✅ 开发完成，等待环境安装
