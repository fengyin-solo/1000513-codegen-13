"""验收项目模板接口：模板版本维护、按任务套用、失败条目重试。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, ApplyPayload, EntryPayload, PageResult
from app.services.template import template_service

router = APIRouter(prefix="/api/verify-templates", tags=["验收项目模板"])


@router.get("", response_model=PageResult[dict])
def list_templates(
    keyword: str | None = Query(default=None, description="按模板名称检索"),
    status: str | None = Query(default=None, description="待生效、生效中、已停用"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """列出模板版本；旧版停用后仍可在此查看。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = template_service.list_templates(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{template_id}", response_model=dict)
def get_template(template_id: int) -> dict:
    template = template_service.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return template


@router.post("", response_model=ActionResult)
def create_template(payload: EntryPayload) -> ActionResult:
    """新建模板或新版本；至少要有模板名称、版本号与一条验收项目。"""
    template, missing = template_service.create_template(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"模板信息不完整：{'、'.join(missing)}")
    return ActionResult(ok=True, message="模板已创建（待生效）", entry=template)


@router.post("/{template_id}/activate", response_model=ActionResult)
def activate_template(template_id: int) -> ActionResult:
    """生效新版：同名旧版自动停用，停用版本仅供查看。"""
    template, message = template_service.activate_template(template_id)
    if template is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=template)


@router.patch("/{template_id}", response_model=ActionResult)
def update_template(template_id: int, payload: EntryPayload) -> ActionResult:
    """生效模板只能调整关联任务，验收标准改动必须走换版。"""
    template, message = template_service.update_template(template_id, payload.values)
    if template is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=template)


@router.post("/apply", response_model=ActionResult)
def apply_template(payload: ApplyPayload) -> ActionResult:
    """按关联任务把生效模板的验收项目与标准套用到待验收单据。

    套用是部分成功语义：成功的直接生成验收单，失败的进失败面板并写明缺失原因，
    返回体里带成功/失败明细，供面板分别展示。
    """
    summary, message = template_service.apply_template(payload.template_id, payload.task_code)
    if summary is None:
        return ActionResult(ok=False, message=message)
    ok = bool(summary.get("套用成功"))
    return ActionResult(ok=ok, message=message, entry=summary)


@router.get("/failures/list")
def list_failures(
    keyword: str | None = Query(default=None, description="按验收单/任务/设备编号检索"),
    kind: str | None = Query(default=None, description="缺失类型：设备编号缺失、验收项目缺失"),
    status: str | None = Query(default=None, description="待修正、已放弃"),
) -> dict:
    """失败面板：单独列出没套用成功的条目及缺失说明。"""
    items = template_service.list_failures(keyword=keyword, kind=kind, status=status)
    return {"total": len(items), "items": items}


@router.post("/failures/{failure_id}/retry", response_model=ActionResult)
def retry_failure(failure_id: int) -> ActionResult:
    """修正设备或模板后重试单条失败，成功即补建验收单并从失败面板移除。"""
    entry, message = template_service.retry_failure(failure_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.delete("/failures/{failure_id}", response_model=ActionResult)
def dismiss_failure(failure_id: int) -> ActionResult:
    ok, message = template_service.dismiss_failure(failure_id)
    return ActionResult(ok=ok, message=message)
