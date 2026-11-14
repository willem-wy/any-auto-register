# LK888 (灵刻 AI) 自动化签到插件

每日自动签到获取 0.1 算力积分。

## 功能特性

- ✅ 协议模式登录（无需浏览器）
- ✅ 每日自动签到
- ✅ XOR 加密算法（逆向工程）
- ✅ 设备标识固定（按账号哈希）
- ✅ 行为包模拟（反爬虫）
- ✅ 验证码支持（数学题 + 纯数字）

## 快速开始

### 1. 安装依赖

```bash
# 使用项目虚拟环境
source .venv/bin/activate

# 安装 curl_cffi（如果未安装）
pip install curl_cffi
```

### 2. 运行签到

```bash
# 基本用法
python test_lk888_checkin.py \
  --email dirkegirzi@necub.com \
  --password wy7374520 \
  --captcha 8125

# 使用第二个测试账号
python test_lk888_checkin.py \
  --email gasekox228@calirona.com \
  --password wy7374520 \
  --captcha 5006
```

### 3. 定时任务

```bash
# 编辑 crontab
crontab -e

# 添加每日 8:00 签到任务
0 8 * * * cd /path/to/any-auto-register && .venv/bin/python test_lk888_checkin.py --email <邮箱> --password <密码> --captcha <验证码> >> /tmp/lk888_checkin.log 2>&1
```

## 验证码识别

当前支持两种验证码类型：

1. **数学题**：`2 x 3 = ?` → 答案 `6`
2. **纯数字**：4 位数字 → 答案 `8125`

### 自动识别（待实现）

```python
# 方案 A：OCR 识别
from PIL import Image
import pytesseract

def recognize_captcha(image_path):
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, config='--psm 7')
    # 解析数学题或提取数字
    ...

# 方案 B：第三方验证码服务
# 使用打码平台 API（如超级鹰、云打码）
```

### 手动输入

```bash
# 运行脚本后会保存验证码图片到 /tmp/lk888_captcha.png
# 查看图片后手动输入答案
open /tmp/lk888_captcha.png  # macOS
```

## 插件集成

### 作为平台插件使用

```python
from platforms.lk888.plugin import LK888Platform
from core.base_platform import RegisterConfig

config = RegisterConfig(executor_type="protocol")
platform = LK888Platform(config=config)

# 查询账号状态
account = Account(
    platform="lk888",
    email="dirkegirzi@necub.com",
    password="wy7374520",
    token="<saved_token>"
)

result = platform.execute_action("daily_checkin", account, {
    "captcha_answer": "8125"
})

print(result)
```

### API 调用

```python
from platforms.lk888.core import LK888Client
from core.executors.protocol import ProtocolExecutor

executor = ProtocolExecutor()
client = LK888Client(executor=executor)

# 登录
captcha_id, captcha_img = client.get_captcha()
login_result = client.login(
    email="dirkegirzi@necub.com",
    password="wy7374520",
    captcha_id=captcha_id,
    captcha_answer="8125"
)

# 签到
checkin_result = client.checkin(token=login_result["token"])
```

## 加密算法

### XOR 混淆加密

来源：`https://ai778.cc/assets/JiaMi-YflxZtvo.js`

```python
# 密钥生成
I_ARR = [188,125,42,166,175,21,53,39,111,122,214,134,92,108,3,33,63,102,67,255,152,119,164,104,166,113,195,231,106,99,61,121]

def decode_key():
    e = 137
    result = []
    for n in range(len(I_ARR)):
        result.append(chr(I_ARR[n] ^ e))
        e = (e * 17 + 23) & 0xFF
    return ''.join(result)

# 结果：5Mmhj96mnRi@aHxcFFtA-kWRWilQGwVK
```

### 加密流程

1. 生成随机前缀：`xxxxx.nnn@xxxxxx-xxxx=xxxxxx`
2. 拼接：`prefix + "|" + value`
3. 每个字节 +7 mod 256
4. 与密钥循环 XOR
5. 反转字节数组
6. Base64 编码

### 监控加密更新

```bash
# 检查加密文件是否更新
curl -s https://ai778.cc/login | grep -o 'assets/JiaMi-[a-zA-Z0-9_-]*\.js'

# 如果文件名变化，需要重新分析加密逻辑
```

## 文件结构

```
platforms/lk888/
├── __init__.py              # 包初始化
├── plugin.py                # 平台插件类
├── core.py                  # 核心 API 实现
└── protocol_checkin.py      # 签到 Worker

test_lk888_checkin.py        # 独立测试脚本
docs/LK888_PROTOCOL.md       # 完整协议文档
```

## 测试账号

| 邮箱 | 密码 | 状态 |
|------|------|------|
| dirkegirzi@necub.com | wy7374520 | ✅ 已验证 |
| gasekox228@calirona.com | wy7374520 | 待测试 |

## 常见问题

### Q: 验证码答案错误？

A: 验证码有两种类型：
- 数学题：`2 x 3 = ?` → `6`
- 纯数字：`8125` → `8125`

查看 `/tmp/lk888_captcha.png` 确认类型。

### Q: Token 加密失败？

A: Token 需要使用同样的 XOR 函数加密，然后作为 `token` 头（小写）发送。

### Q: 设备标识需要固定吗？

A: 是的，设备标识基于账号 SHA256 哈希生成，同一账号始终使用相同 ID。

### Q: 如何检测加密算法更新？

A: 监控 `JiaMi-*.js` 文件名变化，文件名包含哈希值，更新后会变化。

## 参考资料

- [完整协议文档](../../docs/LK888_PROTOCOL.md)
- [加密 JS 源码](https://ai778.cc/assets/JiaMi-YflxZtvo.js)
- [登录 API 源码](https://ai778.cc/assets/DengLuApi-UMlyYzPm.js)

## 更新日志

### 2026-10-14
- ✅ 完成加密算法逆向工程
- ✅ 验证登录 + 签到流程
- ✅ 创建平台插件
- ✅ 创建独立测试脚本
- ✅ 编写完整协议文档
