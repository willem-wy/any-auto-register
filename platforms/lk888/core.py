"""LK888 协议核心实现

加密算法：XOR 混淆（来自 JiaMi-YflxZtvo.js）
- 密钥：I_ARR 数组 XOR 生成
- 流程：随机前缀 + 值 → 字节+7 → XOR密钥 → 反转 → Base64

API 端点：
- 验证码：GET /houduan/denglu/tuxingyzm/get
- 登录：POST /houduan/denglu/mima/denglu
- 签到：POST /houduan/marketing/qiandao
"""
from __future__ import annotations

import base64
import hashlib
import json
import random
import string
import time
from typing import Callable, Optional


# ── 加密常量（来自 JiaMi-YflxZtvo.js） ──
I_ARR = [
    188, 125, 42, 166, 175, 21, 53, 39, 111, 122, 214, 134, 92, 108, 3, 33,
    63, 102, 67, 255, 152, 119, 164, 104, 166, 113, 195, 231, 106, 99, 61, 121
]


def _decode_key() -> str:
    """从 I_ARR 生成 32 字节密钥"""
    e = 137
    result = []
    for n in range(len(I_ARR)):
        result.append(chr(I_ARR[n] ^ e))
        e = (e * 17 + 23) & 0xFF
    return ''.join(result)


SECRET_KEY = _decode_key()  # 5Mmhj96mnRi@aHxcFFtA-kWRWilQGwVK


def _gen_random_prefix() -> str:
    """生成随机前缀：xxxxx.nnn@xxxxxx-xxxx=xxxxxx"""
    p1 = ''.join(random.choices(string.ascii_lowercase, k=5))
    n1 = ''.join(random.choices(string.digits, k=3))
    p2 = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase, k=6))
    p3 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    p4 = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=6))
    return f'{p1}.{n1}@{p2}-{p3}={p4}'


def xor_encrypt(value: str) -> str:
    """
    XOR 加密（用于密码和 Token）

    流程：
    1. 生成随机前缀
    2. 拼接：prefix + "|" + value
    3. 每个字节 +7 mod 256
    4. 与密钥循环 XOR
    5. 反转字节数组
    6. Base64 编码
    """
    prefix = _gen_random_prefix()
    plain = prefix + '|' + value

    # 字节 +7
    t = [(b + 7) % 256 for b in plain.encode('utf-8')]

    # XOR 密钥
    key_bytes = SECRET_KEY.encode('utf-8')
    xored = [t[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(t))]

    # 反转
    xored.reverse()

    # Base64
    return base64.b64encode(bytes(xored)).decode('utf-8')


def xor_decrypt(encrypted: str) -> str:
    """XOR 解密（用于验证）"""
    decoded = base64.b64decode(encrypted)
    reversed_bytes = decoded[::-1]

    key_bytes = SECRET_KEY.encode('utf-8')
    xored = [reversed_bytes[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(reversed_bytes))]

    t = [(b - 7) % 256 for b in xored]
    plain = bytes(t).decode('utf-8')

    return plain.split('|', 1)[1]


def gen_device_id(account: str) -> str:
    """
    基于账号生成固定设备标识
    - 同一账号始终生成相同 ID
    - 格式：web_ + SHA256(account)[:32]
    """
    h = hashlib.sha256(account.encode('utf-8')).hexdigest()
    return 'web_' + h[:32]


def gen_behavior() -> dict:
    """生成行为包（模拟用户行为）"""
    return {
        "v": 1,
        "ts": int(time.time() * 1000),
        "nonce": ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)),
        "qidong": 1,
        "yichang": 0,
        "tingliu": random.randint(100000, 500000),
        "shoujiao": random.randint(100, 200),
        "shubiao": {
            "yangben": random.randint(50, 100),
            "zong": random.randint(200, 500),
            "sujun": random.randint(500, 1500),
            "subiao": random.randint(1000, 2000),
            "zhixiandu": round(random.uniform(0.05, 0.15), 2)
        },
        "dianji": random.randint(2, 5),
        "jianpan": {
            "anzhu": {"n": random.randint(1, 3), "jun": random.randint(50, 150), "biao": 0},
            "jiange": {"n": 0, "jun": 0, "biao": 0}
        },
        "chumo": 0,
        "zidonghua": {
            "webdriver": 0, "wutu": 0, "cdc": 0,
            "lingchuang": 0, "jiachrome": 0, "wuyuyan": 0
        }
    }


class LK888ApiError(RuntimeError):
    """带业务 code 的接口错误（如 4001 图形验证码答案错误、429 限流）。"""

    def __init__(self, code, msg: str):
        super().__init__(f"{msg}（code={code}）")
        self.code = code
        self.msg = msg


class LK888Client:
    """LK888 API 客户端"""

    BASE_URL = "https://ai778.cc"
    SITE_DOMAIN = "ai778.cc"

    def __init__(
        self,
        *,
        executor,
        log_fn: Callable[[str], None] = print,
    ):
        self.ex = executor
        self.log = log_fn
        self._token = ""
        self._user_id = ""

    def _browser_headers(self, referer_path: str = "/") -> dict:
        """生成完整浏览器指纹头（与 ProtocolExecutor 指纹一致）"""
        h = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-site": "same-origin",
            "Referer": f"{self.BASE_URL}{referer_path}",
            "Origin": self.BASE_URL,
            "Cookie": f"x-hng=lang=zh-CN&domain={self.SITE_DOMAIN}",
        }
        if hasattr(self.ex, 's') and hasattr(self.ex.s, 'headers'):
            for key in ("user-agent", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform", "accept-language"):
                val = self.ex.s.headers.get(key)
                if val:
                    h[key] = val
        return h

    def get_captcha(self) -> tuple[str, str]:
        """
        获取图形验证码

        Returns:
            (captcha_id, captcha_image_base64)
        """
        self.log("获取图形验证码...")
        r = self.ex.get(f"{self.BASE_URL}/houduan/denglu/tuxingyzm/get")

        if r.status_code != 200:
            raise RuntimeError(f"获取验证码失败：HTTP {r.status_code}")

        try:
            data = r.json()
        except Exception:
            raise RuntimeError("获取验证码失败：响应解析错误")

        if data.get("code") != 200:
            raise LK888ApiError(data.get("code"), f"获取验证码失败：{data.get('msg', 'unknown')}")

        captcha_id = data["data"]["验证码ID"]
        captcha_img = data["data"]["图片base64"]

        # 去掉 data URI 前缀
        if ',' in captcha_img[:50]:
            captcha_img = captcha_img.split(',', 1)[1]

        self.log(f"验证码 ID: {captcha_id}")
        return captcha_id, captcha_img

    def login(
        self,
        email: str,
        password: str,
        captcha_id: str,
        captcha_answer: str,
        device_id: str = "",
    ) -> dict:
        """
        密码登录

        Args:
            email: 邮箱账号
            password: 明文密码
            captcha_id: 验证码 ID
            captcha_answer: 验证码答案
            device_id: 设备标识（已存库的优先复用，不传则按账号生成）

        Returns:
            {"token": "...", "user_id": "...", "expires": "..."}
        """
        self.log(f"登录账号：{email}")

        encrypted_pw = xor_encrypt(password)
        device_id = device_id or gen_device_id(email)

        payload = {
            "账号": email,
            "密码": encrypted_pw,
            "设备类型": "web",
            "设备标识": device_id,
            "使用语言": "zh-CN",
            "图形验证码ID": captcha_id,
            "图形验证码答案": captcha_answer,
            "行为包": json.dumps(gen_behavior()),
        }

        headers = self._browser_headers("/login")
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/denglu/mima/denglu",
            headers=headers,
            data=json.dumps(payload),
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"登录失败：HTTP {r.status_code}")

        if data.get("code") != 200:
            raise LK888ApiError(data.get("code"), f"登录失败：{data.get('msg', 'unknown')}")

        self._token = data["data"]["token"]
        self._user_id = str(data["data"].get("用户 id", ""))
        expires = data["data"].get("过期时间", "")

        self.log(f"登录成功 (user_id={self._user_id}, expires={expires})")

        return {
            "token": self._token,
            "user_id": self._user_id,
            "expires": expires,
        }

    def checkin(self, token: Optional[str] = None) -> dict:
        """
        每日签到

        Args:
            token: 登录获得的 Token（如果不传则使用内部缓存）

        Returns:
            签到结果
        """
        token = token or self._token
        if not token:
            raise RuntimeError("未登录，无法签到")

        self.log("执行签到...")

        encrypted_token = xor_encrypt(token)
        headers = self._browser_headers("/")
        headers["token"] = encrypted_token
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/marketing/qiandao",
            headers=headers,
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"签到失败：HTTP {r.status_code}")

        if data.get("code") == 200:
            reward = data.get("data", {}).get("奖励金额", 0)
            total = data.get("data", {}).get("总奖励", 0)
            consecutive = data.get("data", {}).get("连续天数", 0)
            self.log(f"签到成功：+{reward} 算力 (连续{consecutive}天，总{total})")
        elif data.get("code") == 400:
            self.log(f"今日已签到：{data.get('msg', '')}")
        else:
            raise LK888ApiError(data.get("code"), f"签到失败：{data.get('msg', 'unknown')}")

        return data

    def get_balance(self, token: Optional[str] = None) -> dict:
        """
        查询余额

        Args:
            token: 登录 Token（不传则使用内部缓存）

        Returns:
            {"余额": 0, "空间": "geren"}
        """
        token = token or self._token
        if not token:
            raise RuntimeError("未登录，无法查询余额")

        encrypted_token = xor_encrypt(token)
        headers = self._browser_headers("/")
        headers["token"] = encrypted_token
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/user/chaxunyue",
            headers=headers,
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"查询余额失败：HTTP {r.status_code}")

        if data.get("code") != 200:
            raise LK888ApiError(data.get("code"), f"查询余额失败：{data.get('msg', 'unknown')}")

        return data.get("data", {}) or {}

    def get_user_info(self, token: Optional[str] = None) -> dict:
        """
        获取用户信息（当前接口可得的字段：余额/空间）

        Args:
            token: 登录 Token（不传则使用内部缓存）

        Returns:
            {"余额": 0, "空间": "geren"}
        """
        return self.get_balance(token=token)

    def get_email_otp(
        self,
        email: str,
        captcha_id: str,
        captcha_answer: str,
    ) -> bool:
        """
        发送邮箱验证码

        Args:
            email: 目标邮箱
            captcha_id: 图形验证码 ID
            captcha_answer: 图形验证码答案

        Returns:
            True 表示发送成功
        """
        self.log(f"发送邮箱验证码到 {email}...")

        encrypted_email = xor_encrypt(email)

        payload = {
            "邮箱": encrypted_email,
            "图形验证码ID": captcha_id,
            "图形验证码答案": captcha_answer,
        }

        headers = self._browser_headers("/login")
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/denglu/mail/huoquyanzhengma",
            headers=headers,
            data=json.dumps(payload),
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"发送邮箱验证码失败：HTTP {r.status_code}")

        if data.get("code") != 200:
            raise LK888ApiError(data.get("code"), f"发送邮箱验证码失败：{data.get('msg', 'unknown')}")

        self.log("邮箱验证码已发送")
        return True

    def email_register(
        self,
        email: str,
        otp: str,
        captcha_id: str,
        captcha_answer: str,
        device_id: str = "",
        attribution: Optional[dict] = None,
    ) -> dict:
        """
        邮箱验证码登录/注册（同一接口，新邮箱自动注册）

        Args:
            email: 邮箱账号
            otp: 邮箱验证码
            captcha_id: 图形验证码 ID
            captcha_answer: 图形验证码答案
            device_id: 设备标识（已存库的优先复用，不传则按账号生成）
            attribution: 归因字段（对齐 Web 端 ct()，如 {"yonghu": 邀请码, "推广渠道码": ...}）

        Returns:
            {"token": "...", "user_id": "...", "device_id": "...", "expires": "..."}
        """
        self.log(f"邮箱注册/登录：{email}")

        device_id = device_id or gen_device_id(email)

        # Web 端注册会附带 ct() 归因字段（域名 + URL 参数捕获），注册赠送/邀请绑定依赖它
        payload = {
            "邮箱": email,
            "验证码": otp,
            "设备类型": "web",
            "设备标识": device_id,
            "使用语言": "zh-CN",
            "图形验证码ID": captcha_id,
            "图形验证码答案": captcha_answer,
            "行为包": json.dumps(gen_behavior()),
            "域名": self.SITE_DOMAIN,
            **(attribution or {}),
        }

        headers = self._browser_headers("/login")
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/denglu/mail/denglu",
            headers=headers,
            data=json.dumps(payload),
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"邮箱注册失败：HTTP {r.status_code}")

        if data.get("code") != 200:
            raise LK888ApiError(data.get("code"), f"邮箱注册失败：{data.get('msg', 'unknown')}")

        self._token = data["data"]["token"]
        self._user_id = str(data["data"].get("用户id", "") or data["data"].get("用户 id", ""))
        expires = data["data"].get("过期时间", "")

        self.log(f"注册成功 (user_id={self._user_id})")

        return {
            "token": self._token,
            "user_id": self._user_id,
            "device_id": device_id,
            "expires": expires,
        }

    def get_phone_otp(
        self,
        phone: str,
        captcha_id: str,
        captcha_answer: str,
    ) -> bool:
        """
        发送手机验证码

        Args:
            phone: 手机号（含国际区号，如 +8613800138000）
            captcha_id: 图形验证码 ID
            captcha_answer: 图形验证码答案

        Returns:
            True 表示发送成功
        """
        self.log(f"发送手机验证码到 {phone}...")

        encrypted_phone = xor_encrypt(phone)

        payload = {
            "手机号": encrypted_phone,
            "图形验证码ID": captcha_id,
            "图形验证码答案": captcha_answer,
        }

        headers = self._browser_headers("/login")
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/denglu/shoujihao/huoquyanzhengma",
            headers=headers,
            data=json.dumps(payload),
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"发送手机验证码失败：HTTP {r.status_code}")

        if data.get("code") != 200:
            raise LK888ApiError(data.get("code"), f"发送手机验证码失败：{data.get('msg', 'unknown')}")

        self.log("手机验证码已发送")
        return True

    def phone_register(
        self,
        phone: str,
        otp: str,
        captcha_id: str,
        captcha_answer: str,
    ) -> dict:
        """
        手机号验证码登录/注册（同一接口，新号自动注册）

        Args:
            phone: 手机号（含国际区号）
            otp: 短信验证码
            captcha_id: 图形验证码 ID
            captcha_answer: 图形验证码答案

        Returns:
            {"token": "...", "user_id": "...", "expires": "..."}
        """
        self.log(f"手机号注册/登录：{phone}")

        device_id = gen_device_id(phone)

        payload = {
            "手机号": phone,
            "验证码": otp,
            "设备类型": "web",
            "设备标识": device_id,
            "使用语言": "zh-CN",
            "图形验证码ID": captcha_id,
            "图形验证码答案": captcha_answer,
            "行为包": json.dumps(gen_behavior()),
        }

        headers = self._browser_headers("/login")
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/denglu/shoujihao/denglu",
            headers=headers,
            data=json.dumps(payload),
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"手机号注册失败：HTTP {r.status_code}")

        if data.get("code") != 200:
            raise LK888ApiError(data.get("code"), f"手机号注册失败：{data.get('msg', 'unknown')}")

        self._token = data["data"]["token"]
        self._user_id = str(data["data"].get("用户id", "") or data["data"].get("用户 id", ""))
        expires = data["data"].get("过期时间", "")

        self.log(f"手机号注册成功 (user_id={self._user_id})")

        return {
            "token": self._token,
            "user_id": self._user_id,
            "expires": expires,
        }

    def check_password_status(self, token: Optional[str] = None) -> dict:
        """
        查询密码状态（是否已设置密码）

        Args:
            token: 登录 Token（不传则使用内部缓存）

        Returns:
            密码状态信息
        """
        token = token or self._token
        if not token:
            raise RuntimeError("未登录，无法查询密码状态")

        encrypted_token = xor_encrypt(token)
        headers = self._browser_headers("/")
        headers["token"] = encrypted_token
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/user/chaxunmimazhuangtai",
            headers=headers,
            data=json.dumps({}),
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"查询密码状态失败：HTTP {r.status_code}")

        if data.get("code") != 200:
            raise RuntimeError(f"查询密码状态失败：{data.get('msg', 'unknown')}")

        return data.get("data", {})

    def set_password(self, password: str, token: Optional[str] = None) -> bool:
        """
        设置密码（注册后首次设置）

        Args:
            password: 要设置的密码
            token: 登录 Token（不传则使用内部缓存）

        Returns:
            True 表示设置成功
        """
        token = token or self._token
        if not token:
            raise RuntimeError("未登录，无法设置密码")

        self.log(f"设置密码...")

        encrypted_password = xor_encrypt(password)
        encrypted_token = xor_encrypt(token)

        headers = self._browser_headers("/")
        headers["token"] = encrypted_token
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/user/shezhimima",
            headers=headers,
            data=json.dumps({
                "密码": encrypted_password,
                "确认密码": encrypted_password,
            }),
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"设置密码失败：HTTP {r.status_code}")

        if data.get("code") != 200:
            raise RuntimeError(f"设置密码失败：{data.get('msg', 'unknown')}")

        self.log("密码设置成功")
        return True

    def create_api_key(
        self,
        name: str = "pp-auto",
        strategy: str = "综合最优",
        limit: int = 0,
        token: Optional[str] = None,
    ) -> dict:
        """
        创建 API Key

        Args:
            name: 密钥名称
            strategy: 渠道策略（综合最优/速度优先/价格优先）
            limit: 限额（0 表示不限）
            token: 登录 Token（不传则使用内部缓存）

        Returns:
            {"api_key": "sk-...", "id": 12345, ...}
        """
        token = token or self._token
        if not token:
            raise RuntimeError("未登录，无法创建 API Key")

        self.log(f"创建 API Key (name={name})...")

        encrypted_token = xor_encrypt(token)
        headers = self._browser_headers("/")
        headers["token"] = encrypted_token
        headers["Content-Type"] = "application/json"

        r = self.ex.post(
            f"{self.BASE_URL}/houduan/apikey/create",
            headers=headers,
            data=json.dumps({
                "name": name,
                "strategy": strategy,
                "limit": limit,
            }),
        )

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"创建 API Key 失败：HTTP {r.status_code}")

        if data.get("code") != 200:
            raise RuntimeError(f"创建 API Key 失败：{data.get('msg', 'unknown')}")

        result = data.get("data", {})
        api_key = result.get("api_key", "")
        self.log(f"API Key 创建成功: {api_key[:20]}...")

        return result
