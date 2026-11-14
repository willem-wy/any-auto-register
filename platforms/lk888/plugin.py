"""LK888 (灵刻 AI) 平台插件

功能：
- 协议模式邮箱注册
- 协议模式手机号注册（接码平台）
- 协议模式登录
- 每日自动签到（0.1 算力积分）
- 账号有效性检测

加密方式：XOR 混淆（JiaMi-YflxZtvo.js）
"""
from core.base_platform import BasePlatform, Account, AccountStatus, RegisterConfig
from core.base_mailbox import BaseMailbox
from core.registration import OtpSpec, ProtocolMailboxAdapter, RegistrationContext, RegistrationResult
from core.registry import register

import hashlib
import time

# 固定邀请码：注册时默认带入（任务 extra.invite_code 可覆盖）
FIXED_INVITE_CODE = "LBHPA808YC9EG47H"


@register
class LK888Platform(BasePlatform):
    name = "lk888"
    display_name = "灵刻 AI (LK888)"
    version = "1.0.0"

    # 仅支持协议模式
    supported_executors = ["protocol"]
    supported_identity_modes = ["mailbox", "phone"]

    def __init__(self, config: RegisterConfig = None, mailbox: BaseMailbox = None):
        super().__init__(config)
        self.mailbox = mailbox

    def _get_identity_provider_name(self) -> str:
        """检查是否使用手机号注册模式"""
        mode = str(self.config.extra.get("identity_provider", "") or "").strip().lower()
        if mode in ("phone", "sms", "shoujihao"):
            return "phone"
        return super()._get_identity_provider_name()

    def _prepare_registration_password(self, password: str | None) -> str | None:
        # LK888 使用固定密码或用户提供的密码
        return password or "wy7374520"

    def _map_checkin_result(self, result: dict) -> dict:
        """映射签到结果"""
        checkin_data = result.get("checkin_result", {})
        data = checkin_data.get("data", {})

        return {
            "email": result["email"],
            "token": result["token"],
            "user_id": result["user_id"],
            "status": AccountStatus.REGISTERED,
            "extra": {
                "reward": data.get("奖励金额", 0),
                "total_reward": data.get("总奖励", 0),
                "consecutive_days": data.get("连续天数", 0),
                "total_days": data.get("累计天数", 0),
            }
        }

    def _map_register_result(self, result: dict) -> RegistrationResult:
        """映射注册结果"""
        return RegistrationResult(
            email=result["email"],
            password=result.get("password", ""),
            user_id=result.get("user_id", ""),
            token=result.get("token", ""),
            status=AccountStatus.REGISTERED,
            extra={
                "token": result.get("token", ""),
                "device_id": result.get("device_id", ""),
                "api_key": result.get("api_key", ""),
            },
        )

    @staticmethod
    def _build_attribution(ctx) -> dict:
        """提取归因字段（邀请码 → yonghu，字段名对齐 Web 端 ct()）

        邀请码默认使用 FIXED_INVITE_CODE；任务 extra.invite_code 可覆盖。
        """
        extra = getattr(ctx, "extra", None) or {}
        invite_code = str(extra.get("invite_code") or "").strip() or FIXED_INVITE_CODE
        return {"yonghu": invite_code}

    def build_protocol_mailbox_adapter(self):
        """构建协议邮箱适配器（用于自动注册流程）"""
        return ProtocolMailboxAdapter(
            result_mapper=lambda ctx, result: self._map_register_result(result),
            worker_builder=lambda ctx, artifacts: __import__(
                "platforms.lk888.protocol_mailbox",
                fromlist=["LK888RegisterWorker"],
            ).LK888RegisterWorker(
                executor=artifacts.executor,
                log_fn=ctx.log,
            ),
            register_runner=lambda worker, ctx, artifacts: worker.run(
                email=ctx.identity.email,
                password=ctx.password or "",
                otp_callback=artifacts.otp_callback,
                captcha_solver=artifacts.captcha_solver,
                attribution=self._build_attribution(ctx),
            ),
            otp_spec=OtpSpec(
                keyword="Verification",
                timeout=120,
                wait_message="等待 LK888 邮箱验证码...",
                success_label="邮箱验证码",
            ),
            use_executor=True,
            use_captcha=True,
        )

    def register(self, email: str = None, password: str = None) -> Account:
        """重写注册方法：支持手机号注册模式"""
        if self._get_identity_provider_name() == "phone":
            return self._register_by_phone(password)
        return super().register(email=email, password=password)

    def _register_by_phone(self, password: str = None) -> Account:
        """手机号注册流程"""
        from core.registration import RegistrationResult
        from core.registration.helpers import build_phone_callbacks

        resolved_password = self._prepare_registration_password(password)
        self.log(f"手机号注册模式")

        ctx = RegistrationContext(
            platform_name=self.name,
            platform_display_name=self.display_name,
            platform=self,
            identity=None,
            config=self.config,
            email=None,
            password=resolved_password,
            log_fn=self.log,
        )

        phone_callback, phone_cleanup = build_phone_callbacks(ctx, service=self.name)
        if not phone_callback:
            raise RuntimeError(
                "手机号注册需要配置 SMS provider（接码平台），"
                "请在设置页启用并配置 SMS-Activate / HeroSMS / SMSBower"
            )

        captcha_solver = self._make_captcha() if self._has_configured_captcha(self._resolve_captcha_solver()) else None

        try:
            from core.executors.protocol import ProtocolExecutor
            from platforms.lk888.protocol_phone import LK888PhoneRegisterWorker

            ex = ProtocolExecutor(proxy=self.config.proxy)
            try:
                worker = LK888PhoneRegisterWorker(executor=ex, log_fn=self.log)
                result = worker.run(
                    password=resolved_password or "",
                    phone_callback=phone_callback,
                    captcha_solver=captcha_solver,
                )
            finally:
                ex.close()

            reg_result = RegistrationResult(
                email=result["email"],
                password=result.get("password", ""),
                user_id=result.get("user_id", ""),
                token=result.get("token", ""),
                status=AccountStatus.REGISTERED,
                extra={
                    "token": result.get("token", ""),
                    "device_id": result.get("device_id", ""),
                    "api_key": result.get("api_key", ""),
                },
            )
            return self._account_from_registration_result(reg_result)
        finally:
            if phone_cleanup:
                phone_cleanup()

    def check_valid(self, account: Account) -> bool:
        """
        检测账号是否有效

        优先用 token 查余额：200=有效（同时记录余额供面板展示），401=失效；
        失效时自动走密码登录重登换新 token（并落库），无 token 时回退 api_key 校验
        """
        self._last_check_overview = {}
        token = str(account.token or "").strip()
        if token:
            from core.executors.protocol import ProtocolExecutor
            from platforms.lk888.core import LK888ApiError, LK888Client

            ex = ProtocolExecutor(proxy=self.config.proxy if self.config else None)
            try:
                client = LK888Client(executor=ex, log_fn=self.log)
                try:
                    balance = client.get_balance(token=token)
                except LK888ApiError as exc:
                    if exc.code != 401:
                        self._last_check_overview = {"check_error": f"余额查询失败: {exc}"}
                        return False
                    self.log(f"{account.email}: token 已失效，尝试密码重登")
                    refreshed = self._refresh_token(account)
                    if not refreshed.get("ok"):
                        self._last_check_overview = {
                            "check_error": f"{exc}；重登失败: {refreshed.get('error')}"
                        }
                        return False
                    try:
                        balance = client.get_balance(token=str(refreshed.get("token") or ""))
                    except LK888ApiError as retry_exc:
                        self._last_check_overview = {
                            "check_error": f"重登成功但余额查询失败: {retry_exc}"
                        }
                        return False
                except Exception as exc:
                    self._last_check_overview = {"check_error": f"余额查询异常: {exc}"}
                    return False
            except Exception as exc:
                self._last_check_overview = {"check_error": f"检测异常: {exc}"}
                return False
            finally:
                ex.close()

            self._last_check_overview = {
                "balance": balance.get("余额"),
                "space": balance.get("空间", ""),
                "check_error": "",
            }
            return True

        api_key = (account.extra or {}).get("api_key", "")
        if api_key:
            from core.executors.protocol import ProtocolExecutor

            ex = ProtocolExecutor(proxy=self.config.proxy if self.config else None)
            try:
                r = ex.get(
                    "https://api.ai778.cc/v1/models",
                    headers={
                        "authorization": f"Bearer {api_key}",
                        "accept": "application/json",
                    },
                )
                return r.status_code == 200
            finally:
                ex.close()

        return False

    def get_last_check_overview(self) -> dict:
        return dict(getattr(self, "_last_check_overview", {}) or {})

    def _refresh_token(self, account: Account) -> dict:
        """token 失效后用密码登录重新签发新 token（手机号/邮箱通用）并落库。"""
        from core.executors.protocol import ProtocolExecutor
        from platforms.lk888.core import gen_device_id
        from platforms.lk888.protocol_mailbox import LK888RegisterWorker

        ident = str(account.email or "").strip()
        if not ident:
            return {"ok": False, "error": "账号缺少登录标识（邮箱/手机号），无法重登"}

        password = str(account.password or "").strip()
        if not password:
            return {"ok": False, "error": "账号未保存密码，无法密码重登"}

        if self._relogin_on_cooldown(account, password):
            return {
                "ok": False,
                "error": "同一密码近期重登已失败，已跳过重复尝试（更新密码后会自动重试）",
            }

        kind = "手机号" if "@" not in ident else "邮箱"

        try:
            captcha_solver = self._make_captcha()
        except Exception as exc:
            self.log(f"验证码 provider 不可用（{exc}），改用内置本地识别")
            captcha_solver = None

        device_id = str((account.extra or {}).get("device_id") or "").strip() or gen_device_id(ident)
        ex = ProtocolExecutor(proxy=self.config.proxy if self.config else None)
        try:
            try:
                result = LK888RegisterWorker(executor=ex, log_fn=self.log).login_with_password(
                    account=ident,
                    password=password,
                    device_id=device_id,
                    captcha_solver=captcha_solver,
                )
            except Exception as exc:
                self._mark_relogin_failed(account, password)
                self.log(f"{ident}: 密码重登失败（{exc}）")
                return {"ok": False, "error": str(exc)}
        finally:
            ex.close()

        token = str(result.get("token") or "").strip()
        if not token:
            return {"ok": False, "error": "密码登录未返回新 token"}

        account.token = token
        if not account.user_id and result.get("user_id"):
            account.user_id = str(result["user_id"])
        account.extra["device_id"] = device_id
        overview = (account.extra or {}).get("account_overview")
        if isinstance(overview, dict):
            # 置空而非 pop：overview 落库是 merge 语义，pop 不会删除已存在的键
            overview["relogin_failed_at"] = None
            overview["relogin_failed_pw"] = ""
        self._persist_account(account)
        self.log(f"{ident}: 密码登录成功（{kind}账号），token 已更新")
        return {"ok": True, "token": token, "user_id": account.user_id}

    # 同一密码重登失败后的冷却期：避免每小时巡检反复用错误凭据触发风控
    RELOGIN_FAILURE_COOLDOWN_SECONDS = 12 * 3600

    @staticmethod
    def _relogin_overview(account: Account) -> dict:
        overview = (account.extra or {}).get("account_overview")
        return overview if isinstance(overview, dict) else {}

    @classmethod
    def _relogin_on_cooldown(cls, account: Account, password: str) -> bool:
        overview = cls._relogin_overview(account)
        try:
            failed_at = float(overview.get("relogin_failed_at") or 0)
        except (TypeError, ValueError):
            return False
        return (
            failed_at > 0
            and time.time() - failed_at < cls.RELOGIN_FAILURE_COOLDOWN_SECONDS
            and str(overview.get("relogin_failed_pw") or "") == cls._password_digest(password)
        )

    @classmethod
    def _mark_relogin_failed(cls, account: Account, password: str) -> None:
        overview = (account.extra or {}).get("account_overview")
        if not isinstance(overview, dict):
            overview = {}
            account.extra["account_overview"] = overview
        overview["relogin_failed_at"] = time.time()
        overview["relogin_failed_pw"] = cls._password_digest(password)
        cls._persist_account(account)

    @staticmethod
    def _password_digest(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def _persist_account(account: Account) -> None:
        from core.db import save_account

        save_account(account)


    def get_platform_actions(self) -> list:
        """返回平台支持的操作列表"""
        return [
            {
                "id": "daily_checkin",
                "label": "每日签到",
                "params": []
            },
            {
                "id": "refresh_token",
                "label": "刷新 Token",
                "params": []
            },
            {
                "id": "set_password",
                "label": "设置密码",
                "params": [
                    {"key": "password", "label": "密码", "type": "string"}
                ]
            },
            {
                "id": "create_api_key",
                "label": "创建 API Key",
                "params": [
                    {"key": "name", "label": "密钥名称", "type": "string"},
                    {"key": "strategy", "label": "渠道策略", "type": "select", "options": [
                        {"value": "综合最优", "label": "综合最优"},
                        {"value": "速度优先", "label": "速度优先"},
                        {"value": "价格优先", "label": "价格优先"},
                    ]}
                ]
            },
            {
                "id": "get_account_state",
                "label": "查询账号状态",
                "params": []
            },
        ]

    def execute_action(self, action_id: str, account: Account, params: dict) -> dict:
        """执行平台操作"""
        if action_id == "daily_checkin":
            return self._do_checkin(account, params)
        elif action_id == "refresh_token":
            return self._do_refresh_token(account)
        elif action_id == "set_password":
            return self._do_set_password(account, params)
        elif action_id == "create_api_key":
            return self._do_create_api_key(account, params)
        elif action_id == "get_account_state":
            return self._get_account_state(account)
        raise NotImplementedError(f"未知操作：{action_id}")

    def _do_checkin(self, account: Account, params: dict) -> dict:
        """执行签到（用 token 直签；失效走密码重登）"""
        try:
            from core.executors.protocol import ProtocolExecutor
            from platforms.lk888.core import LK888ApiError, LK888Client

            token = str(account.token or "").strip()
            if not token:
                return {"ok": False, "error": "账号缺少 token，请重新注册获取"}

            ex = ProtocolExecutor(proxy=self.config.proxy if self.config else None)
            try:
                client = LK888Client(executor=ex, log_fn=self.log)
                try:
                    checkin_result = client.checkin(token=token)
                except LK888ApiError as exc:
                    if exc.code != 401:
                        raise
                    self.log("token 已失效，尝试密码重登后重试签到")
                    refreshed = self._refresh_token(account)
                    if not refreshed.get("ok"):
                        return {"ok": False, "error": f"token 已失效且重登失败：{refreshed.get('error')}"}
                    token = str(refreshed.get("token") or "")
                    checkin_result = client.checkin(token=token)
            finally:
                ex.close()

            data = checkin_result.get("data", {}) or {}
            return {
                "ok": True,
                "data": {
                    "token": token,
                    "user_id": account.user_id,
                    "already_checked_in": checkin_result.get("code") == 400,
                    "checkin": data,
                }
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _do_refresh_token(self, account: Account) -> dict:
        """密码登录重登，换取新 token（用于手动刷新失效 token）"""
        try:
            result = self._refresh_token(account)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if not result.get("ok"):
            return {"ok": False, "error": str(result.get("error") or "刷新失败")}
        return {
            "ok": True,
            "data": {
                "user_id": result.get("user_id", ""),
                "message": "Token 已刷新",
            },
        }

    def _do_set_password(self, account: Account, params: dict) -> dict:
        """设置密码（需要 token 认证）"""
        try:
            from core.executors.protocol import ProtocolExecutor
            from platforms.lk888.core import LK888Client

            password = params.get("password", "")
            if not password:
                return {"ok": False, "error": "请提供密码"}

            token = str(account.token or "").strip()
            if not token:
                return {"ok": False, "error": "账号缺少 token，请重新注册获取"}

            ex = ProtocolExecutor(proxy=self.config.proxy if self.config else None)
            try:
                client = LK888Client(executor=ex, log_fn=self.log)
                client.set_password(password, token=token)
            finally:
                ex.close()

            account.password = password
            return {
                "ok": True,
                "data": {"message": "密码设置成功"},
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _do_create_api_key(self, account: Account, params: dict) -> dict:
        """创建 API Key"""
        try:
            from core.executors.protocol import ProtocolExecutor
            from platforms.lk888.core import LK888Client

            token = str(account.token or "").strip()
            if not token:
                return {"ok": False, "error": "账号缺少 token，请重新注册获取"}

            name = params.get("name", "pp-auto")
            strategy = params.get("strategy", "综合最优")

            ex = ProtocolExecutor(proxy=self.config.proxy if self.config else None)
            try:
                client = LK888Client(executor=ex, log_fn=self.log)
                key_data = client.create_api_key(name=name, strategy=strategy, token=token)
            finally:
                ex.close()

            api_key = key_data.get("api_key", "")
            # 存储到 account.extra
            if not account.extra:
                account.extra = {}
            account.extra["api_key"] = api_key

            return {
                "ok": True,
                "data": {
                    "api_key": api_key,
                    "id": key_data.get("id"),
                    "name": key_data.get("密钥名称", name),
                    "strategy": key_data.get("渠道策略", strategy),
                },
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _get_account_state(self, account: Account) -> dict:
        """查询账号状态（含实时余额）"""
        data = {
            "email": account.email,
            "user_id": account.user_id,
            "status": account.status.value,
            "token_valid": bool(account.token),
            "extra": account.extra or {},
        }
        token = str(account.token or "").strip()
        if token:
            try:
                from core.executors.protocol import ProtocolExecutor
                from platforms.lk888.core import LK888Client

                ex = ProtocolExecutor(proxy=self.config.proxy if self.config else None)
                try:
                    balance = LK888Client(executor=ex, log_fn=self.log).get_balance(token=token)
                finally:
                    ex.close()
                data["balance"] = balance.get("余额")
                data["space"] = balance.get("空间", "")
            except Exception as exc:
                data["token_valid"] = False
                data["check_error"] = str(exc)
        return {"ok": True, "data": data}

    def get_quota(self, account: Account) -> dict:
        """查询账号配额（实时余额）"""
        data = {
            "status": account.status.value,
            "user_id": account.user_id,
            "email": account.email,
            "platform": self.name,
        }
        token = str(account.token or "").strip()
        if token:
            try:
                from core.executors.protocol import ProtocolExecutor
                from platforms.lk888.core import LK888Client

                ex = ProtocolExecutor(proxy=self.config.proxy if self.config else None)
                try:
                    balance = LK888Client(executor=ex, log_fn=self.log).get_balance(token=token)
                finally:
                    ex.close()
                data["balance"] = balance.get("余额")
                data["space"] = balance.get("空间", "")
            except Exception as exc:
                data["error"] = str(exc)
        return data
