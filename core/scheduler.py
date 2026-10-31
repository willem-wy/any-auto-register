"""定时任务调度 - trial 到期、余额巡检、自动签到"""
from datetime import datetime, timedelta, timezone
import threading
import time

from sqlmodel import Session, select

from .account_graph import load_account_graphs, patch_account_graph
from .base_platform import AccountStatus, RegisterConfig
from .config_store import config_store
from .db import engine, AccountModel, TaskModel
from .platform_accounts import build_platform_account
from .registry import get, load_all

# 自动巡检/签到的默认平台与周期，可在 configs 表覆盖：
#   scheduler_auto_platform          默认 lk888，置空表示关闭自动任务
#   scheduler_balance_interval_hours 默认 1
#   scheduler_checkin_hour           默认 8（北京时间每天 08:00 签到一次，错过时刻会在下一轮补跑）
DEFAULT_AUTO_PLATFORM = "lk888"
DEFAULT_BALANCE_INTERVAL_HOURS = 1.0
DEFAULT_CHECKIN_HOUR = 8
CHECKIN_TZ = timezone(timedelta(hours=8))
TICK_SECONDS = 30


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_float(key: str, default: float) -> float:
    try:
        return float(config_store.get(key, str(default)) or default)
    except (TypeError, ValueError):
        return default


class Scheduler:
    def __init__(self):
        self._running = False
        self._thread: threading.Thread = None
        self._last_trial_check = 0.0
        self._last_balance_check = 0.0
        self._checkin_retry_at = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        # 从持久化基准恢复巡检节奏，避免重启后立即触发一次全量检测/密码重登
        self._last_balance_check = _read_float("scheduler_last_balance_at", 0.0)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[Scheduler] 已启动")

    def stop(self):
        self._running = False

    def _loop(self):
        # 等 task_runtime 完成启动后再派发任务
        time.sleep(5)
        while self._running:
            now = time.time()
            try:
                if now - self._last_trial_check >= 3600:
                    self.check_trial_expiry()
                    self._last_trial_check = now

                if now - self._last_balance_check >= self._interval_seconds(
                    "scheduler_balance_interval_hours", DEFAULT_BALANCE_INTERVAL_HOURS
                ):
                    self.run_balance_check()
                    self._last_balance_check = now

                if self._checkin_due(now):
                    self.run_auto_checkin()
            except Exception as e:
                print(f"[Scheduler] 错误: {e}")

            for _ in range(TICK_SECONDS):
                if not self._running:
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # 自动余额巡检 / 签到
    # ------------------------------------------------------------------

    def run_balance_check(self) -> None:
        """创建一次全量有效性检测任务；LK888 的 check_valid 会查询余额，401 时自动密码重登。"""
        platform = self._auto_platform()
        if not platform:
            return
        if not self._has_accounts(platform):
            return
        from application.tasks import TASK_TYPE_ACCOUNT_CHECK_ALL, create_account_check_all_task
        from services.task_runtime import task_runtime

        if self._has_active_task(TASK_TYPE_ACCOUNT_CHECK_ALL, platform):
            print(f"[Scheduler] 余额巡检跳过：{platform} 已有检测任务在运行")
            return
        task = create_account_check_all_task(platform, limit=500)
        task_runtime.wake_up()
        self._set_last_balance_ts(time.time())
        print(f"[Scheduler] 余额巡检已排队: {platform} task={task['task_id']}")

    def run_auto_checkin(self) -> None:
        """为自动平台的全部账号创建签到任务，签到失败会尝试一次密码重登。"""
        platform = self._auto_platform()
        if not platform:
            return
        account_ids = self._account_ids(platform)
        if not account_ids:
            return
        from application.checkin_report import schedule_checkin_report
        from application.tasks import TASK_TYPE_PLATFORM_ACTION, create_platform_action_task
        from services.task_runtime import task_runtime

        if self._has_active_task(TASK_TYPE_PLATFORM_ACTION, platform):
            print(f"[Scheduler] 自动签到跳过：{platform} 已有操作任务在运行，5 分钟后重试")
            self._checkin_retry_at = time.time() + 300
            return

        task_ids = []
        for account_id in account_ids:
            task = create_platform_action_task({
                "platform": platform,
                "account_id": account_id,
                "action_id": "daily_checkin",
                "params": {},
            })
            task_ids.append(task["task_id"])
        task_runtime.wake_up()
        schedule_checkin_report(task_ids, platform)
        self._set_last_checkin_ts(time.time())
        print(f"[Scheduler] 自动签到已排队: {platform} {len(task_ids)} 个账号")

    def _auto_platform(self) -> str:
        return (config_store.get("scheduler_auto_platform", DEFAULT_AUTO_PLATFORM) or "").strip()

    @staticmethod
    def _interval_seconds(key: str, default_hours: float) -> float:
        # 下限 3 分钟，避免误配置导致高频请求
        return max(_read_float(key, default_hours), 0.05) * 3600

    def _checkin_due(self, now: float) -> bool:
        """每天在固定时刻（默认北京时间 08:00）签到一次；错过时刻会在下一轮补跑。"""
        if now < self._checkin_retry_at:
            return False
        scheduled = self._checkin_scheduled_ts(now)
        last = _read_float("scheduler_last_checkin_at", 0.0)
        if last <= 0:
            # 首次部署从今天/当前时刻起算，下一个签到时刻才开始自动签到（首个签到留给用户手动触发）
            config_store.set("scheduler_last_checkin_at", str(max(now, scheduled)))
            return False
        return now >= scheduled and last < scheduled

    @staticmethod
    def _checkin_scheduled_ts(now: float) -> float:
        hour = min(max(int(_read_float("scheduler_checkin_hour", DEFAULT_CHECKIN_HOUR)), 0), 23)
        local = datetime.fromtimestamp(now, CHECKIN_TZ)
        return local.replace(hour=hour, minute=0, second=0, microsecond=0).timestamp()

    @staticmethod
    def _set_last_checkin_ts(ts: float) -> None:
        config_store.set("scheduler_last_checkin_at", str(ts))

    @staticmethod
    def _set_last_balance_ts(ts: float) -> None:
        config_store.set("scheduler_last_balance_at", str(ts))

    @staticmethod
    def _has_accounts(platform: str) -> bool:
        with Session(engine) as session:
            return session.exec(
                select(AccountModel.id).where(AccountModel.platform == platform).limit(1)
            ).first() is not None

    @staticmethod
    def _account_ids(platform: str) -> list[int]:
        with Session(engine) as session:
            ids = session.exec(
                select(AccountModel.id).where(AccountModel.platform == platform)
            ).all()
        return [int(account_id) for account_id in ids if account_id]

    @staticmethod
    def _has_active_task(task_type: str, platform: str) -> bool:
        from application.tasks import ACTIVE_TASK_STATUSES, TASK_STATUS_PENDING

        statuses = [TASK_STATUS_PENDING, *ACTIVE_TASK_STATUSES]
        with Session(engine) as session:
            return session.exec(
                select(TaskModel.id)
                .where(TaskModel.type == task_type)
                .where(TaskModel.platform == platform)
                .where(TaskModel.status.in_(statuses))
                .limit(1)
            ).first() is not None

    # ------------------------------------------------------------------
    # Trial 到期检查
    # ------------------------------------------------------------------

    def check_trial_expiry(self):
        """检查 trial 到期账号，更新状态"""
        now = int(datetime.now(timezone.utc).timestamp())
        with Session(engine) as s:
            accounts = s.exec(select(AccountModel)).all()
            graphs = load_account_graphs(s, [int(acc.id or 0) for acc in accounts if acc.id])
            updated = 0
            for acc in accounts:
                graph = graphs.get(int(acc.id or 0), {})
                if graph.get("lifecycle_status") != "trial":
                    continue
                trial_end_time = int((graph.get("overview") or {}).get("trial_end_time") or 0)
                if trial_end_time and trial_end_time < now:
                    acc.updated_at = datetime.now(timezone.utc)
                    patch_account_graph(s, acc, lifecycle_status=AccountStatus.EXPIRED.value)
                    s.add(acc)
                    updated += 1
            s.commit()
            if updated:
                print(f"[Scheduler] {updated} 个 trial 账号已到期")

    def check_accounts_valid(self, platform: str = None, limit: int = 50):
        """批量检测账号有效性（同步执行，保留给脚本/调试使用）"""
        load_all()
        with Session(engine) as s:
            q = select(AccountModel)
            if platform:
                q = q.where(AccountModel.platform == platform)
            q = q.order_by(AccountModel.created_at.desc(), AccountModel.id.desc())
            accounts = s.exec(q.limit(limit)).all()
            graphs = load_account_graphs(s, [int(acc.id or 0) for acc in accounts if acc.id])
            accounts = [
                acc for acc in accounts
                if graphs.get(int(acc.id or 0), {}).get("lifecycle_status") in {"registered", "trial", "subscribed"}
            ]

        results = {"valid": 0, "invalid": 0, "error": 0}
        for acc in accounts:
            try:
                PlatformCls = get(acc.platform)
                plugin = PlatformCls(config=RegisterConfig())
                with Session(engine) as s:
                    current = s.get(AccountModel, acc.id)
                    if not current:
                        continue
                    account_obj = build_platform_account(s, current)
                valid = plugin.check_valid(account_obj)
                with Session(engine) as s:
                    a = s.get(AccountModel, acc.id)
                    if a:
                        a.updated_at = datetime.now(timezone.utc)
                        summary_updates = {"checked_at": _utcnow_iso(), "valid": valid}
                        if hasattr(plugin, "get_last_check_overview"):
                            summary_updates.update(plugin.get_last_check_overview() or {})
                        patch_account_graph(
                            s,
                            a,
                            summary_updates=summary_updates,
                        )
                        s.add(a)
                        s.commit()
                if valid:
                    results["valid"] += 1
                else:
                    results["invalid"] += 1
            except Exception:
                results["error"] += 1
        return results


scheduler = Scheduler()
