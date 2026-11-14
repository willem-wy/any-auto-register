"""LK888 协议手机号注册 worker。

流程：
  1. 从接码平台获取手机号
  2. 获取图形验证码 → 识别 → 发送手机验证码（重试）
  3. 从接码平台获取短信验证码
  4. 获取新图形验证码 → 识别 → 提交注册/登录
  5. 设置密码
  6. 创建 API Key
"""
from __future__ import annotations

import random
import re
import time
from typing import Callable, Optional

from platforms.lk888.core import LK888ApiError, LK888Client, gen_device_id
from platforms.lk888.protocol_mailbox import (
    CAPTCHA_MAX_ATTEMPTS,
    _try_recognize_captcha,
)


def _human_delay(lo: float = 1.0, hi: float = 3.0) -> None:
    time.sleep(random.uniform(lo, hi))


class LK888PhoneRegisterWorker:
    """LK888 手机号注册 Worker。"""

    def __init__(self, *, executor, log_fn: Callable[[str], None] = print):
        self.client = LK888Client(executor=executor, log_fn=log_fn)
        self.log = log_fn

    def run(
        self,
        *,
        password: str,
        phone_callback: Optional[Callable[[], str]] = None,
        captcha_solver=None,
    ) -> dict:
        if not phone_callback:
            raise RuntimeError("手机号注册需要 phone_callback（接码平台）")

        # ── Step 1: 获取手机号 ──
        phone = phone_callback()
        if not phone:
            raise RuntimeError("接码平台未返回手机号")
        self.log(f"获取手机号: {phone}")

        # ── Step 2: 发送手机验证码 ──
        _human_delay(1.5, 4.0)
        self._send_phone_otp_with_retries(phone, captcha_solver)

        # ── Step 3: 获取短信验证码 ──
        _human_delay(2.0, 5.0)
        otp = phone_callback()
        if not otp:
            raise RuntimeError("未收到短信验证码")
        self.log(f"短信验证码: {otp}")

        # ── Step 4: 提交注册 ──
        _human_delay(1.5, 4.0)
        result = self._register_with_retries(phone, otp, captcha_solver)

        # ── Step 5: 设置密码 ──
        if password:
            _human_delay(2.0, 5.0)
            try:
                self.client.set_password(password, token=result.get("token", ""))
            except Exception as exc:
                self.log(f"设置密码失败（可稍后手动设置）: {exc}")

        # ── Step 6: 创建 API Key ──
        _human_delay(1.5, 3.5)
        api_key = ""
        try:
            key_data = self.client.create_api_key(token=result.get("token", ""))
            api_key = key_data.get("api_key", "")
        except Exception as exc:
            self.log(f"创建 API Key 失败（可稍后手动创建）: {exc}")

        return {
            "email": phone,
            "password": password,
            "token": result.get("token", ""),
            "user_id": result.get("user_id", ""),
            "device_id": gen_device_id(phone),
            "api_key": api_key,
        }

    def _send_phone_otp_with_retries(self, phone: str, captcha_solver) -> None:
        last_err = None
        for attempt in range(1, CAPTCHA_MAX_ATTEMPTS + 1):
            try:
                captcha_id, captcha_img = self.client.get_captcha()
                answer = self._solve_captcha(captcha_img, captcha_solver)
                if not answer:
                    self.log(f"发送手机OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 验证码识别失败，换一张重试")
                    _human_delay(1.5, 3.0)
                    continue
                self.log(f"发送手机OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 验证码答案: {answer}")
                self.client.get_phone_otp(phone, captcha_id, answer)
                return
            except LK888ApiError as exc:
                last_err = exc
                if exc.code == 4001:
                    self.log(f"发送手机OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] {exc.msg}，换一张验证码重试")
                    _human_delay(1.5, 3.0)
                    continue
                if exc.code == 429:
                    self.log(f"发送手机OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] 请求过于频繁，等待 10 秒")
                    _human_delay(8.0, 14.0)
                    continue
                if exc.code == 400 and "频繁" in str(exc.msg):
                    delay = 10
                    m = re.search(r'(\d+)\s*秒', str(exc.msg))
                    if m:
                        delay = int(m.group(1)) + 3
                    self.log(f"发送手机OTP [{attempt}/{CAPTCHA_MAX_ATTEMPTS}] {exc.msg}，等待 {delay} 秒")
                    time.sleep(delay + random.uniform(0, 3))
                    continue
                raise
        raise RuntimeError(
            f"发送手机验证码失败：重试 {CAPTCHA_MAX_ATTEMPTS} 次未成功"
            f"（{last_err or '验证码识别失败'}）"
        )

    def _register_with_retries(self, phone: str, otp: str, captcha_solver) -> dict:
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
                return self.client.phone_register(phone, otp, captcha_id, answer)
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
            f"手机号注册失败：重试 {CAPTCHA_MAX_ATTEMPTS} 次未成功"
            f"（{last_err or '验证码识别失败'}）"
        )

    def _solve_captcha(self, image_base64: str, captcha_solver) -> str:
        if captcha_solver:
            try:
                token = captcha_solver.solve_image(image_base64)
                if token:
                    return str(token)
            except Exception as exc:
                self.log(f"captcha_solver 识别失败: {exc}")
        return _try_recognize_captcha(image_base64)
