from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from application.account_checks import AccountChecksService
from application.checkin_report import schedule_checkin_report
from application.tasks import create_platform_action_task
from core.db import AccountModel, engine
from services.task_runtime import task_runtime

router = APIRouter(prefix="/accounts", tags=["account-checks"])
service = AccountChecksService()


@router.post("/check-all")
def check_all_accounts(platform: str = ""):
    return service.check_all_async(platform)


@router.post("/checkin-all")
def checkin_all_accounts(platform: str = ""):
    """批量签到：为平台下所有账号创建签到任务"""
    with Session(engine) as session:
        statement = select(AccountModel).where(AccountModel.platform == platform)
        models = session.exec(statement).all()
    if not models:
        raise HTTPException(404, "没有找到账号")
    task_ids = []
    for model in models:
        task = create_platform_action_task({
            "platform": platform,
            "account_id": int(model.id or 0),
            "action_id": "daily_checkin",
            "params": {},
        })
        task_ids.append(task["task_id"])
    task_runtime.wake_up()
    schedule_checkin_report(task_ids, platform)
    return {"task_ids": task_ids, "count": len(task_ids)}


@router.post("/{account_id}/check")
def check_account(account_id: int):
    result = service.check_one_async(account_id)
    if not result:
        raise HTTPException(404, "账号不存在")
    return result
