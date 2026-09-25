"""验收确认接口：维护验收单，覆盖开始验收、确认通过、下发返工等动作。

注意路由顺序：/export、/delivery 是固定路径，必须放在 /{entry_id} 之前注册，
否则 "export" 会被当成验收单 id 解析，导出永远 422。
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.verify import DELIVERY_FIELDS, VerifyService

router = APIRouter(prefix="/api/verify", tags=["验收确认"])

service = VerifyService()

LIST_FIELDS = ["验收单号", "关联任务", "设备编号", "验收项目", "验收标准", "验收结论", "验收人员", "验收日期", "验收状态"]
STATUSES = ["待验收", "验收中", "已通过", "需返工"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按验收单号检索"),
    task: str | None = Query(default=None, description="按关联任务检索"),
    device: str | None = Query(default=None, description="按设备编号检索"),
    status: str | None = Query(default=None, description="待验收、验收中、已通过、需返工"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按验收单号、关联任务、设备编号与状态过滤验收确认列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, task=task, device=device, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出验收确认清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "verify", "total": total, "items": items}


@router.get("/delivery")
def export_delivery() -> Response:
    """导出交付清单：确认通过的验收结论生成 CSV 文件供下载。"""
    rows = service.delivery_entries()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["序号", *DELIVERY_FIELDS])
    for index, row in enumerate(rows, start=1):
        writer.writerow([index, *[row.get(field, "") for field in DELIVERY_FIELDS]])
    # 加 BOM 让 Excel 直接打开不乱码
    content = "﻿" + buffer.getvalue()
    filename = f"delivery_list_{date.today().isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条验收单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"验收单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条验收单，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="验收单已登记", entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """修改验收单字段；已返工或已通过的单据不允许改动验收标准与验收结论。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条验收单执行开始验收、确认通过、下发返工；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
