"""验收项目模板接口：维护模板版本，支持按关联任务套用待验收单据并跟踪失败重试。

注意路由顺序：/apply/failures、/apply/retry 是固定路径，必须放在 /{tpl_id}
之前注册，否则会被当成模板 id 解析而报错。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, ApplyResult, EntryPayload, PageResult
from app.services.template import TemplateService

router = APIRouter(prefix="/api/template", tags=["验收项目模板"])

service = TemplateService()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按模板编号或名称检索"),
    status: str | None = Query(default=None, description="生效中、已停用"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按模板编号/名称与状态过滤模板列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/apply/failures")
def list_apply_failures() -> dict[str, Any]:
    """套用失败面板：单独列出没套用成功的条目，写清缺的是设备编号还是验收项目。"""
    failures = service.list_failures()
    return {"total": len(failures), "items": failures}


@router.post("/apply/retry", response_model=ApplyResult)
def retry_apply(payload: EntryPayload) -> ApplyResult:
    """改完数据后重试套用；不传入验收单 id 时重试失败面板里的全部条目。"""
    raw_ids = payload.values.get("entry_ids")
    entry_ids = [int(item) for item in raw_ids] if isinstance(raw_ids, list) else None
    applied, failed, message = service.retry_failures(entry_ids)
    return ApplyResult(ok=True, message=message, applied=applied, failed=failed)


@router.get("/{tpl_id}", response_model=dict)
def get_entry(tpl_id: int) -> dict:
    """读取单个模板明细（含验收条目）；旧版模板同样可以查看，但不能套用。"""
    entry = service.get_entry(tpl_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"模板 {tpl_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一个验收项目模板，缺字段或条目不完整时说明原因而不是静默丢弃。"""
    entry, errors = service.create_entry(payload.values)
    if errors:
        return ActionResult(ok=False, message="；".join(errors))
    return ActionResult(ok=True, message="验收模板已登记并生效", entry=entry)


@router.post("/{tpl_id}/actions", response_model=ActionResult)
def run_action(tpl_id: int, payload: EntryPayload) -> ActionResult:
    """对生效中的模板执行换版升级：生成新版本，旧版置为已停用仅保留查看。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(tpl_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{tpl_id}/apply", response_model=ApplyResult)
def apply_template(tpl_id: int, payload: EntryPayload) -> ApplyResult:
    """把生效中的模板按关联任务套用到待验收单据；套用不成功的条目进失败面板。"""
    task = str(payload.values.get("关联任务") or "").strip() or None
    raw_ids = payload.values.get("entry_ids")
    entry_ids = [int(item) for item in raw_ids] if isinstance(raw_ids, list) else None
    ok, applied, failed, message = service.apply_template(tpl_id, task=task, entry_ids=entry_ids)
    return ApplyResult(ok=ok, message=message, applied=applied, failed=failed)
