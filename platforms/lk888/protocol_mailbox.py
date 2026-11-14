"""LK888 协议邮箱注册 worker。

流程：
  1. 获取图形验证码 → 识别 → 发送邮箱验证码（识别/答案错误时自动换码重试）
  2. 等待邮箱 OTP
  3. 获取新图形验证码 → 识别 → 提交注册/登录（识别/答案错误时自动换码重试）

图形验证码有两种：数学题（如 18+7=? 答案填计算结果）和 4 位数字。
"""
from __future__ import annotations

import base64
import io
import random
import re
import time
import unicodedata
from collections import Counter
from typing import Callable, Optional

from platforms.lk888.core import LK888ApiError, LK888Client, gen_device_id

CAPTCHA_MAX_ATTEMPTS = 6


def _human_delay(lo: float = 1.0, hi: float = 3.0) -> None:
    """模拟人类操作间隔，带随机抖动。"""
    time.sleep(random.uniform(lo, hi))

_OCR_NORMAL = None
_OCR_BETA = None

# ddddocr 对数字/符号的常见误读修正
_DIGIT_FIX = {
    'z': '2', 'Z': '2', 'o': '0', 'O': '0', 'D': '0', 'Q': '0',
    'I': '1', 'l': '1', 'i': '1', 'S': '5', 's': '5', 'B': '8', 'g': '9',
    '一': '2', '入': '2', '公': '2',
}
_OP_FIX = {'×': 'x', 'X': 'x', '＊': 'x', '*': 'x', '十': '+'}


def _get_ocr_models():
    global _OCR_NORMAL, _OCR_BETA
    if _OCR_NORMAL is None:
        import ddddocr
        _OCR_NORMAL = ddddocr.DdddOcr(show_ad=False)
        _OCR_BETA = ddddocr.DdddOcr(show_ad=False, beta=True)
    return _OCR_NORMAL, _OCR_BETA


def _png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _saturation_mask(img, scale: int = 3):
    """保留高饱和彩色笔画和深色笔画，滤掉浅色噪点/干扰字。"""
    from PIL import Image

    rgb = img.convert('RGB')
    rgb = rgb.resize((rgb.width * scale, rgb.height * scale), Image.LANCZOS)
    px = rgb.load()
    w, h = rgb.size
    out = Image.new('L', (w, h), 255)
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            lum = (r * 299 + g * 587 + b * 114) // 1000
            if (mx - mn) > 70 and mx > 120:
                op[x, y] = 0
            elif lum < 110:
                op[x, y] = 0
    return out


def _build_variants(img):
    from PIL import Image, ImageFilter, ImageOps

    g = img.convert('L')
    up = g.resize((g.width * 3, g.height * 3), Image.LANCZOS)
    yield up
    yield ImageOps.autocontrast(up)
    b120 = up.point(lambda p: 0 if p < 120 else 255)
    b140 = up.point(lambda p: 0 if p < 140 else 255)
    yield b120
    yield b140
    yield up.point(lambda p: 0 if p < 160 else 255)
    yield b140.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    yield ImageOps.invert(b140)
    yield _saturation_mask(img)


def _parse_captcha_text(text: str):
    """把 OCR 文本解析成 (kind, answer)，kind 为 'math' 或 'digits'。"""
    if not text:
        return None
    t = unicodedata.normalize('NFKC', text.strip())
    for k, v in _OP_FIX.items():
        t = t.replace(k, v)
    # 数学题：两个 1-2 位操作数（末尾的 =? 及其被误读的残渣忽略）
    m = re.match(r'^(\d{1,2})\s*([+\-x/])\s*(\d{1,2})', t)
    if m:
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        if op == '+':
            r = a + b
        elif op == '-':
            r = a - b
        elif op == 'x':
            r = a * b
        else:
            if b == 0 or a % b:
                return None
            r = a // b
        if 0 <= r <= 999:
            return ('math', str(r))
    # 4 位数字（含常见误读字符修正）
    if re.fullmatch(r'\d{4}', t):
        return ('digits', t)
    fixed = ''.join(_DIGIT_FIX.get(ch, ch) for ch in t)
    if re.fullmatch(r'\d{4}', fixed):
        return ('digits', fixed)
    return None


def _decide(candidates) -> str:
    """数学题优先（操作符是强信号），同类内按出现次数投票。"""
    math_c = Counter(a for k, a in candidates if k == 'math')
    dig_c = Counter(a for k, a in candidates if k == 'digits')
    if math_c:
        return math_c.most_common(1)[0][0]
    if dig_c:
        return dig_c.most_common(1)[0][0]
    return ''


def _try_recognize_captcha(image_base64: str) -> str:
    """本地 OCR 识别验证码，失败返回空字符串。"""
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(base64.b64decode(image_base64))).convert('RGB')
    except Exception:
        return ''

    normal, beta = _get_ocr_models()
    candidates = []
    for variant in _build_variants(img):
        buf = _png_bytes(variant)
        for model in (normal, beta):
            try:
                text = model.classification(buf)
            except Exception:
                continue
            parsed = _parse_captcha_text(text)
            if parsed:
                candidates.append(parsed)

    answer = _decide(candidates)
    if not answer:
        try:
            with open('/tmp/lk888_captcha_failed.png', 'wb') as f:
                f.write(base64.b64decode(image_base64))
        except Exception:
            pass
    return answer


class LK888RegisterWorker:
    """LK888 邮箱注册 Worker。"""

    def __init__(self, *, executor, log_fn: Callable[[str], None] = print):
        self.client = LK888Client(executor=executor, log_fn=log_fn)
        self.log = log_fn

    def run(
        self,
        *,
        email: str,
        password: str,
        otp_callback: Optional[Callable[[], str]] = None,
        captcha_solver=None,
        attribution: Optional[dict] = None,
    ) -> dict:
        # ── Step 1: 获取验证码 → 发送邮箱 OTP ──
        self._send_otp_with_retries(email, captcha_solver)

        # ── Step 2: 获取邮箱 OTP ──
        _human_delay(2.0, 5.0)
        otp = otp_callback() if otp_callback else ""
        if not otp:
            raise RuntimeError("未获取到邮箱验证码")
        self.log(f"邮箱验证码: {otp}")

        # ── Step 3: 获取新验证码 → 提交注册 ──
        _human_delay(1.5, 4.0)
        device_id = gen_device_id(email)
        result = self._register_with_retries(
            email, otp, captcha_solver, device_id=device_id, attribution=attribution
        )

        # ── Step 4: 设置密码（注册后首次设置，用于后续密码登录） ──
        if password:
            _human_delay(2.0, 5.0)
            try:
                self.client.set_password(password, token=result.get("token", ""))
            except Exception as exc:
                self.log(f"设置密码失败（可稍后手动设置）: {exc}")

        # ── Step 5: 创建 API Key ──
        _human_delay(1.5, 3.5)
        api_key = ""
        try:
            key_data = self.client.create_api_key(token=result.get("token", ""))
            api_key = key_data.get("api_key", "")
        except Exception as exc:
            self.log(f"创建 API Key 失败（可稍后手动创建）: {exc}")

        return {
            "email": email,
            "password": password,
            "token": result.get("token", ""),
            "user_id": result.get("user_id", ""),
            "device_id": device_id,
            "api_key": api_key,
        }

    def login_with_password(
        self,
        *,
        account: str,
        password: str,
        device_id: str = "",
        captcha_solver=None,
    ) -> dict:
        """密码登录（邮箱/手机号通用），签发新 token（token 过期自愈）。

        account 传邮箱或手机号均可，服务端按同一接口识别。
        """
        device_id = device_id or gen_device_id(account)
        last_err = None
        for attempt in range(1, CAPTCHA_MAX_ATTEMPTS + 1):
            try:
                captcha_id, captcha_img = self.client.get_captcha()
                answer = self._solve_captcha(captcha_img, captcha_solver)
                if not answer:
                    self.log(f"密码登录 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 验证码识别失败，换一张重试")
                    _human_delay(1.5, 3.0)
                    continue
                self.log(f"密码登录 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 验证码答案: {answer}")
                result = self.client.login(
                    email=account,
                    password=password,
                    captcha_id=captcha_id,
                    captcha_answer=answer,
                    device_id=device_id,
                )
                return {
                    "email": account,
                    "token": result.get("token", ""),
                    "user_id": result.get("user_id", ""),
                    "device_id": device_id,
                }
            except LK888ApiError as exc:
                last_err = exc
                if exc.code == 4001:
                    self.log(f"密码登录 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] {exc.msg}，换一张验证码重试")
                    _human_delay(1.5, 3.0)
                    continue
                if exc.code == 429:
                    self.log(f"密码登录 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 请求过于频繁，等待 10 秒")
                    _human_delay(8.0, 14.0)
                    continue
                if exc.code == 400 and "频繁" in str(exc.msg):
                    delay = 10
                    m = re.search(r'(\d+)\s*秒', str(exc.msg))
                    if m:
                        delay = int(m.group(1)) + 3
                    self.log(f"密码登录 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] {exc.msg}，等待 {delay} 秒")
                    time.sleep(delay + random.uniform(0, 3))
                    continue
                raise
        raise RuntimeError(
            f"密码登录失败：重试 {CAPTCHA_MAX_ATTEMPTS} 次未成功"
            f"（{last_err or '验证码识别失败'}）"
        )

    def _send_otp_with_retries(self, email: str, captcha_solver) -> None:
        last_err = None
        for attempt in range(1, CAPTCHA_MAX_ATTEMPTS + 1):
            try:
                captcha_id, captcha_img = self.client.get_captcha()
                answer = self._solve_captcha(captcha_img, captcha_solver)
                if not answer:
                    self.log(f"发送OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 验证码识别失败，换一张重试")
                    _human_delay(1.5, 3.0)
                    continue
                self.log(f"发送OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 验证码答案: {answer}")
                self.client.get_email_otp(email, captcha_id, answer)
                return
            except LK888ApiError as exc:
                last_err = exc
                if exc.code == 4001:
                    self.log(f"发送OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] {exc.msg}，换一张验证码重试")
                    _human_delay(1.5, 3.0)
                    continue
                if exc.code == 429:
                    self.log(f"发送OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 请求过于频繁，等待 10 秒")
                    _human_delay(8.0, 14.0)
                    continue
                if exc.code == 400 and "频繁" in str(exc.msg):
                    delay = 10
                    m = re.search(r'(\d+)\s*秒', str(exc.msg))
                    if m:
                        delay = int(m.group(1)) + 3
                    self.log(f"发送OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] {exc.msg}，等待 {delay} 秒")
                    time.sleep(delay + random.uniform(0, 3))
                    continue
                raise
        raise RuntimeError(
            f"发送邮箱验证码失败：重试 {CAPTCHA_MAX_ATTEMPTS} 次未成功"
            f"（{last_err or '验证码识别失败'}）"
        )

    def _register_with_retries(
        self,
        email: str,
        otp: str,
        captcha_solver,
        device_id: str = "",
        attribution: Optional[dict] = None,
    ) -> dict:
        last_err = None
        for attempt in range(1, CAPTCHA_MAX_ATTEMPTS + 1):
            try:
                captcha_id, captcha_img = self.client.get_captcha()
                answer = self._solve_captcha(captcha_img, captcha_solver)
                if not answer:
                    self.log(f"注册 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 验证码识别失败，换一张重试")
                    _human_delay(1.5, 3.0)
                    continue
                self.log(f"注册 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 验证码答案: {answer}")
                return self.client.email_register(
                    email, otp, captcha_id, answer, device_id=device_id, attribution=attribution
                )
            except LK888ApiError as exc:
                last_err = exc
                if exc.code == 4001:
                    self.log(f"注册 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] {exc.msg}，换一张验证码重试")
                    _human_delay(1.5, 3.0)
                    continue
                if exc.code == 429:
                    self.log(f"注册 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 请求过于频繁，等待 10 秒")
                    _human_delay(8.0, 14.0)
                    continue
                if exc.code == 400 and "频繁" in str(exc.msg):
                    delay = 10
                    m = re.search(r'(\d+)\s*秒', str(exc.msg))
                    if m:
                        delay = int(m.group(1)) + 3
                    self.log(f"注册 [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] {exc.msg}，等待 {delay} 秒")
                    time.sleep(delay + random.uniform(0, 3))
                    continue
                raise
        raise RuntimeError(
            f"邮箱注册失败：重试 {CAPTCHA_MAX_ATTEMPTS} 次未成功"
            f"（{last_err or '验证码识别失败'}）"
        )

    def _solve_captcha(self, image_base64: str, captcha_solver) -> str:
        """优先使用 captcha_solver，否则使用内置本地识别。"""
        if captcha_solver:
            try:
                token = captcha_solver.solve_image(image_base64)
                if token:
                    return str(token)
            except Exception as exc:
                self.log(f"captcha_solver 识别失败: {exc}")

        return _try_recognize_captcha(image_base64)
