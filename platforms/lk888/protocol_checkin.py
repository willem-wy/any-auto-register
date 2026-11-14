"""LK888 协议签到 worker"""
from __future__ import annotations

import base64
import re
from typing import Callable, Optional

from platforms.lk888.core import LK888Client


def recognize_captcha_image(image_base64: str) -> str:
    """
    识别验证码图片

    支持类型：
    - 数学题：2 x 3 = ? → 6
    - 纯数字：4 位数字 → 8125

    当前使用简单规则识别，后续可接入 OCR
    """
    # 解码 base64 图片
    try:
        img_data = base64.b64decode(image_base64)
        # 保存到临时文件用于调试
        with open('/tmp/lk888_captcha_debug.png', 'wb') as f:
            f.write(img_data)
    except Exception:
        pass

    # TODO: 接入 OCR 识别
    # 当前返回空字符串，需要人工输入或使用验证码服务
    return ""


class LK888CheckinWorker:
    """LK888 签到 Worker"""

    def __init__(
        self,
        *,
        executor,
        log_fn: Callable[[str], None] = print,
    ):
        self.client = LK888Client(executor=executor, log_fn=log_fn)
        self.log = log_fn

    def run(
        self,
        *,
        email: str,
        password: str,
        captcha_callback: Optional[Callable[[str], str]] = None,
    ) -> dict:
        """
        执行登录 + 签到流程

        Args:
            email: 邮箱账号
            password: 明文密码
            captcha_callback: 验证码识别回调 (image_base64) -> answer

        Returns:
            {
                "email": "...",
                "token": "...",
                "user_id": "...",
                "checkin_result": {...}
            }
        """
        # Step 1: 获取验证码
        captcha_id, captcha_img = self.client.get_captcha()

        # Step 2: 识别验证码
        if captcha_callback:
            captcha_answer = captcha_callback(captcha_img)
        else:
            # 尝试自动识别
            captcha_answer = recognize_captcha_image(captcha_img)

        if not captcha_answer:
            raise RuntimeError("验证码识别失败，请提供 captcha_callback")

        self.log(f"验证码答案：{captcha_answer}")

        # Step 3: 登录
        login_result = self.client.login(
            email=email,
            password=password,
            captcha_id=captcha_id,
            captcha_answer=captcha_answer,
        )

        # Step 4: 签到
        checkin_result = self.client.checkin(token=login_result["token"])

        return {
            "email": email,
            "token": login_result["token"],
            "user_id": login_result["user_id"],
            "checkin_result": checkin_result,
        }
