"""小红书平台插件 —— 仅做账号存储与登录态检测，不提供注册/签到流程。

账号凭据来自 ppStudio App 内 WebView 登录后采集的 cookie（credential key = cookie）。
check_valid 只依据 cookie 里的登录标记判定：
匿名访问只带 a1/webId/gid 等设备指纹，web_session 才是登录会话；
从服务器 IP 探测个人信息接口需要 x-s 签名且容易触发风控，不做 HTTP 探测。
"""

from __future__ import annotations

from urllib.parse import unquote

from core.base_platform import Account, BasePlatform, RegisterConfig
from core.registry import register

SESSION_COOKIE = "web_session"


def parse_cookie_map(cookie: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for item in cookie.split(";"):
        separator = item.find("=")
        if separator <= 0:
            continue
        key = item[:separator].strip()
        value = item[separator + 1 :].strip()
        if key:
            pairs[key] = value
    return pairs


def cookie_session(cookie: str) -> str:
    return unquote(parse_cookie_map(cookie).get(SESSION_COOKIE, "")).strip()


@register
class XiaohongshuPlatform(BasePlatform):
    name = "xiaohongshu"
    display_name = "小红书"
    version = "1.0.0"
    # 只用于承载账号；声明 protocol 让默认 RegisterConfig 能实例化（不提供注册流程）
    supported_executors = ["protocol"]
    supported_identity_modes = []
    supported_oauth_providers = []
    capabilities = []

    def __init__(self, config: RegisterConfig = None, mailbox=None):
        super().__init__(config)
        self.mailbox = mailbox
        self._last_check_overview: dict = {}

    def get_last_check_overview(self) -> dict:
        return dict(self._last_check_overview or {})

    def check_valid(self, account: Account) -> bool:
        self._last_check_overview = {}
        cookie = str((account.extra or {}).get("cookie") or "").strip()
        if not cookie:
            self._last_check_overview = {"check_error": "缺少 cookie"}
            return False

        session = cookie_session(cookie)
        if not session:
            self._last_check_overview = {
                "check_error": "cookie 中缺少 web_session，未登录",
            }
            return False

        self._last_check_overview = {
            "login_signal": "cookie",
            "session_hint": f"{session[:4]}****{session[-4:]}"
            if len(session) > 8
            else "********",
        }
        return True
