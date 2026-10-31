"""一键签到批次完成后发送汇总通知。"""
from __future__ import annotations

import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from application.tasks import TERMINAL_TASK_STATUSES, TASK_STATUS_SUCCEEDED
from core.account_graph import load_account_graphs
from core.config_store import config_store
from core.db import AccountModel, TaskModel, engine

CONFIG_KEY = "checkin_report_webhook_url"

_POLL_INTERVAL_SECONDS = 2.0
_BATCH_TIMEOUT_SECONDS = 15 * 60
_MESSAGE_LIMIT = 1950
_TZ = timezone(timedelta(hours=8))


def schedule_checkin_report(task_ids: list[str], platform: str) -> None:
    """后台等待批次结束再发送，避免阻塞 checkin-all 请求。"""
    if not task_ids or not config_store.get(CONFIG_KEY, "").strip():
        return
    threading.Thread(
        target=_wait_and_send,
        args=(tuple(task_ids), platform),
        daemon=True,
        name="checkin-report",
    ).start()


def _wait_and_send(task_ids: tuple[str, ...], platform: str) -> None:
    deadline = time.monotonic() + _BATCH_TIMEOUT_SECONDS
    while True:
        tasks = _load_tasks(task_ids)
        if len(tasks) == len(task_ids) and all(
            task["status"] in TERMINAL_TASK_STATUSES for task in tasks
        ):
            break
        if time.monotonic() >= deadline:
            print("[checkin-report] 等待签到任务超时，跳过通知")
            return
        time.sleep(_POLL_INTERVAL_SECONDS)

    try:
        webhook_url = config_store.get(CONFIG_KEY, "").strip()
        if not webhook_url:
            return
        _post(webhook_url, _build_payload(tasks, platform))
    except Exception as exc:
        print(f"[checkin-report] 通知发送异常: {exc}")


def _load_tasks(task_ids: tuple[str, ...]) -> list[dict]:
    with Session(engine) as session:
        rows = session.exec(select(TaskModel).where(TaskModel.id.in_(task_ids))).all()
        by_id = {task.id: task for task in rows}
        tasks = []
        for task_id in task_ids:
            task = by_id.get(task_id)
            if not task:
                continue
            result = task.get_result() or {}
            tasks.append(
                {
                    "task_id": task.id,
                    "status": task.status,
                    "error": task.error or "",
                    "payload": task.get_payload() or {},
                    "data": result.get("data") or {},
                }
            )
        return tasks


def _build_payload(tasks: list[dict], platform: str) -> dict:
    account_ids = [
        int(task["payload"].get("account_id") or 0)
        for task in tasks
        if int(task["payload"].get("account_id") or 0) > 0
    ]
    with Session(engine) as session:
        accounts = {
            int(model.id): model.email
            for model in session.exec(
                select(AccountModel).where(AccountModel.id.in_(account_ids))
            ).all()
        }
        graphs = load_account_graphs(session, account_ids)

    success = 0
    failed = 0
    rewards = 0.0
    lines: list[str] = []

    for task in tasks:
        account_id = int(task["payload"].get("account_id") or 0)
        email = accounts.get(account_id) or f"账号#{account_id}"
        if task["status"] != TASK_STATUS_SUCCEEDED:
            failed += 1
            lines.append(f"❌ {email}：{task['error'] or task['status']}")
            continue

        success += 1
        data = task["data"] or {}
        checkin = data.get("checkin") or {}
        overview = (graphs.get(account_id) or {}).get("overview") or {}
        parts: list[str] = []

        if data.get("already_checked_in"):
            parts.append("今日已签到")
        else:
            reward = _to_float(checkin.get("奖励金额"))
            if reward is not None:
                rewards += reward
                parts.append(f"+{reward:g}")

        days = checkin.get("累计天数")
        if days not in (None, ""):
            parts.append(f"累计{days}天")
        streak = checkin.get("连续天数")
        if streak not in (None, ""):
            parts.append(f"连签{streak}天")
        if checkin.get("命中里程碑"):
            milestone = checkin.get("里程碑名称") or "里程碑"
            parts.append(f"命中{milestone}")
        balance = _to_float(overview.get("balance"))
        if balance is not None:
            parts.append(f"余额 {balance:g}")

        lines.append(f"✅ {email}：" + ("，".join(parts) if parts else "签到成功"))

    now = datetime.now(_TZ)
    summary = f"{success}/{len(tasks)} 成功，奖励合计 +{rewards:g}"
    if failed:
        summary += f"，失败 {failed}"
    header = [
        f"时间：{now:%Y-%m-%d %H:%M} (UTC+8)",
        f"结果：{summary}",
    ]
    message = "\n".join(header) + "\n\n" + "\n".join(
        f"{index}. {line}" for index, line in enumerate(lines, 1)
    )

    label = platform.upper() if platform else "账号"
    level = "info" if not failed else ("error" if success == 0 else "warn")
    return {
        "title": f"{label} 一键签到报告（{success}/{len(tasks)} 成功）",
        "message": _truncate(message),
        "level": level,
        "source": "pi",
    }


def _post(webhook_url: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    # Caddy 内网入口使用内部 CA 签发的证书，容器内不预置该 CA
    context = ssl._create_unverified_context() if webhook_url.startswith("https://") else None
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:
            body = response.read().decode("utf-8", "replace")
            print(f"[checkin-report] webhook HTTP {response.status}: {body[:200]}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(f"[checkin-report] webhook HTTP {exc.code}: {body[:200]}")
    except Exception as exc:
        print(f"[checkin-report] webhook 发送失败: {exc}")


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truncate(message: str) -> str:
    if len(message) <= _MESSAGE_LIMIT:
        return message
    return message[: _MESSAGE_LIMIT - 1] + "…"
