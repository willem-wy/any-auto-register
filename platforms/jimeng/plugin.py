"""即梦平台插件"""
import random
import string
from typing import Optional

from core.base_platform import BasePlatform, Account, AccountStatus, RegisterConfig
from core.base_mailbox import BaseMailbox
from core.registration import (
    BrowserRegistrationAdapter,
    OtpSpec,
    RegistrationCapability,
    RegistrationResult,
)
from core.registry import register

from platforms.jimeng.core import JIMENG_DOMAIN, UA


@register
class JimengPlatform(BasePlatform):
    """即梦 AI 平台插件"""

    name = "jimeng"
    display_name = "即梦 AI"
    version = "1.0.0"
    supported_executors = ["headless", "headed"]  # 仅支持浏览器模式
    supported_identity_modes = ["mailbox"]  # 邮箱注册
    protocol_captcha_order = ("2captcha", "capsolver", "auto")

    # 平台能力
    capabilities = [
        "query_state",      # 查询账号状态/积分
        "check_valid",      # 检测账号有效性
    ]

    def __init__(self, config: RegisterConfig = None, mailbox: BaseMailbox = None):
        super().__init__(config)
        self.mailbox = mailbox

    def _prepare_registration_password(self, password: Optional[str]) -> Optional[str]:
        """生成随机密码"""
        if password:
            return password
        return "".join(random.choices(string.ascii_letters + string.digits + "!@#$", k=16))

    def _map_jimeng_result(self, result: dict) -> RegistrationResult:
        """映射注册结果"""
        if not result.get("success"):
            raise RuntimeError(f"即梦注册失败：{result.get('error', '未知错误')}")

        return RegistrationResult(
            email=result["email"],
            password="",  # 即梦使用 Cookie，不需要密码
            token=result.get("session_id", ""),
            status=AccountStatus.REGISTERED,
            extra={
                "session_id_ss": result.get("session_id_ss", ""),
                "cookies": result.get("cookies", {}),
                "user_info": result.get("user_info", {}),
                "platform": "jimeng",
            },
        )

    def build_browser_registration_adapter(self):
        """构建浏览器注册适配器"""
        return BrowserRegistrationAdapter(
            result_mapper=lambda ctx, result: self._map_jimeng_result(result),
            browser_worker_builder=lambda ctx, artifacts: __import__(
                "platforms.jimeng.browser_register", fromlist=["JimengBrowserRegister"]
            ).JimengBrowserRegister(
                captcha=artifacts.captcha_solver,
                headless=(ctx.executor_type == "headless"),
                proxy=ctx.proxy,
                otp_callback=artifacts.otp_callback,
                log_fn=ctx.log,
            ),
            browser_register_runner=lambda worker, ctx, artifacts: worker.run(
                email=ctx.identity.email,
                password=ctx.password,
            ),
            capability=RegistrationCapability(
                oauth_headless_requires_browser_reuse=False,
            ),
            otp_spec=OtpSpec(wait_message="等待即梦验证码..."),
            use_captcha_for_mailbox=True,
        )

    def check_valid(self, account: Account) -> bool:
        """检测账号有效性"""
        session_id = account.token or account.extra.get("session_id", "")
        if not session_id:
            return False

        try:
            from curl_cffi import requests as curl_req

            # 访问账号信息接口
            response = curl_req.get(
                f"https://{JIMENG_DOMAIN}/api/user/info",
                headers={
                    "Cookie": f"sessionid={session_id}",
                    "User-Agent": UA,
                    "Referer": f"https://{JIMENG_DOMAIN}/",
                },
                impersonate="chrome124",
                timeout=15,
            )

            if response.status_code == 200:
                data = response.json()
                # 检查是否返回用户信息
                if data.get("data") or data.get("user"):
                    return True
            return False
        except Exception as e:
            self.log(f"️ 账号检测失败：{e}")
            return False

    def get_account_status(self, account: Account) -> dict:
        """获取账号状态和积分信息"""
        session_id = account.token or account.extra.get("session_id", "")
        if not session_id:
            return {"error": "缺少 session_id"}

        try:
            from curl_cffi import requests as curl_req

            # 获取用户信息
            user_response = curl_req.get(
                f"https://{JIMENG_DOMAIN}/api/user/info",
                headers={
                    "Cookie": f"sessionid={session_id}",
                    "User-Agent": UA,
                },
                impersonate="chrome124",
                timeout=15,
            )

            # 获取积分余额
            credit_response = curl_req.get(
                f"https://{JIMENG_DOMAIN}/api/credit/balance",
                headers={
                    "Cookie": f"sessionid={session_id}",
                    "User-Agent": UA,
                },
                impersonate="chrome124",
                timeout=15,
            )

            result = {
                "valid": user_response.status_code == 200,
                "user_info": user_response.json() if user_response.status_code == 200 else None,
                "credit_info": credit_response.json() if credit_response.status_code == 200 else None,
            }

            return result
        except Exception as e:
            return {"error": str(e)}

    def get_platform_actions(self) -> list:
        """返回平台支持的操作列表"""
        return [
            {"id": "check_account", "label": "检测账号有效性", "params": []},
            {"id": "query_credit", "label": "查询积分余额", "params": []},
            {"id": "refresh_cookie", "label": "刷新 Cookie", "params": []},
        ]

    def execute_action(self, action_id: str, account: Account, params: dict) -> dict:
        """执行平台操作"""
        if action_id == "check_account":
            return {"valid": self.check_valid(account)}
        elif action_id == "query_credit":
            return self.get_account_status(account)
        elif action_id == "refresh_cookie":
            return {"error": "Cookie 刷新需要重新登录，请使用注册流程"}
        else:
            return {"error": f"未知操作：{action_id}"}
