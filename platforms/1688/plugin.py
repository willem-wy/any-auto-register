"""1688 平台插件 —— 仅做账号存储与登录态检测，不提供注册/签到流程。

账号凭据来自 ppStudio App 内 WebView 登录后采集的 cookie（credential key = cookie）。
check_valid 只依据 cookie 里的登录标记判定：
work.1688.com 是卖家后台，买家账号即使已登录也会被弹回 pass.1688.com，
从服务器 IP 发起探测还会命中风控，用 HTTP 探测会误判有效账号为失效。
"""

from __future__ import annotations

from urllib.parse import unquote

from core.base_platform import Account, BasePlatform, RegisterConfig
from core.registry import register

LOGGED_OUT_FLAGS = {"", "false", "0"}


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


def cookie_member_id(cookie: str) -> str:
    pairs = parse_cookie_map(cookie)
    for key in ("__cn_logon_id__", "cookie2"):
        raw = pairs.get(key, "")
        if not raw:
            continue
        value = unquote(raw)
        if key == "__cn_logon_id__":
            return value.strip()
        # cookie2 形如 "<timestamp>_<memberId>_<n>"
        parts = value.split("_")
        if len(parts) >= 2 and parts[1]:
            return parts[1]
    return ""


@register
class Alibaba1688Platform(BasePlatform):
    name = "1688"
    display_name = "1688"
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

        pairs = parse_cookie_map(cookie)
        flag = unquote(pairs.get("__cn_logon__", "")).strip().lower()
        if flag in LOGGED_OUT_FLAGS:
            self._last_check_overview = {
                "check_error": "cookie 中 __cn_logon__ 未标记登录",
                "member_id": cookie_member_id(cookie),
            }
            return False

        self._last_check_overview = {
            "member_id": cookie_member_id(cookie),
            "login_signal": "cookie",
        }
        return True
