"""验收项目模板业务规则：版本换版、套用校验与失败重试都收在这里。

模板按「模板编号」成族，同一族里只有一版生效中；换版会生成新版本行并把旧版置为
已停用（仅保留查看）。套用只针对待验收单据，已下发返工的单据验收标准不允许被
模板覆盖。
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "template"
VERIFY_MODULE = "verify"
REQUIRED_FIELDS = ["模板编号", "模板名称"]
ITEM_REQUIRED_FIELDS = ["设备编号", "验收项目", "验收标准"]
DEFAULT_SUGGESTION = "符合验收标准，建议通过"
STATUS_ACTIVE = "生效中"
STATUS_RETIRED = "已停用"
# 只有待验收单据允许套用模板；需返工单据的验收标准已被锁定
APPLIABLE_STATUS = "待验收"


def _next_version(version: str) -> str:
    """V1.0 → V1.1；不带小数的版本号直接进位；认不出的格式在后面补一段。"""
    text = str(version or "").strip()
    match = re.match(r"^(V?)(\d+)\.(\d+)$", text, re.IGNORECASE)
    if match:
        prefix = match.group(1).upper() or "V"
        return f"{prefix}{match.group(2)}.{int(match.group(3)) + 1}"
    match = re.match(r"^(V?)(\d+)$", text, re.IGNORECASE)
    if match:
        prefix = match.group(1).upper() or "V"
        return f"{prefix}{int(match.group(2)) + 1}"
    return f"{text or 'V1'}.1"


def _normalize_items(raw_items: Any) -> tuple[list[dict[str, str]], list[str]]:
    """把传入的模板条目整理成统一结构；返回整理结果与错误说明。"""
    if not isinstance(raw_items, list) or not raw_items:
        return [], ["模板至少需要一条验收条目"]
    items: list[dict[str, str]] = []
    errors: list[str] = []
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            errors.append(f"第 {index} 条验收条目格式不正确")
            continue
        item = {field: str(raw.get(field) or "").strip() for field in ITEM_REQUIRED_FIELDS}
        missing = [field for field in ITEM_REQUIRED_FIELDS if not item[field]]
        if missing:
            errors.append(f"第 {index} 条验收条目缺少：{'、'.join(missing)}")
            continue
        item["结论建议"] = str(raw.get("结论建议") or "").strip() or DEFAULT_SUGGESTION
        items.append(item)
    return items, errors


class TemplateService:
    def __init__(self) -> None:
        # 套用失败面板：以验收单 id 为键，改好数据重试成功后移除
        self._failures: dict[int, dict[str, Any]] = {}

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("模板编号", "")) or keyword in str(row.get("模板名称", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [
            {**row, "条目数": len(row.get("items", []))}
            for row in rows[start:start + size]
        ]
        return page_rows, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        return {**row, "条目数": len(row.get("items", []))}

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, [f"缺少必填字段：{'、'.join(missing)}"]
        code = str(values["模板编号"]).strip()
        if any(row.get("模板编号") == code for row in store.rows(MODULE)):
            return None, [f"模板编号 {code} 已存在，如需更新请使用换版升级"]
        items, errors = _normalize_items(values.get("items"))
        if errors:
            return None, errors
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["模板编号"] = code
        entry["模板名称"] = str(values["模板名称"]).strip()
        entry["版本号"] = str(values.get("版本号") or "").strip() or "V1.0"
        entry["生效日期"] = date.today().isoformat()
        entry["模板状态"] = STATUS_ACTIVE
        entry["status"] = STATUS_ACTIVE
        entry["pending"] = False
        entry["abnormal"] = False
        entry["items"] = items
        rows.append(entry)
        return {**entry, "条目数": len(items)}, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"模板 {entry_id} 不存在或已归档"
        if action != "换版升级":
            return None, f"动作「{action}」不属于验收模板可执行范围"
        if entry.get("status") != STATUS_ACTIVE:
            return None, "旧版模板仅保留查看，请对当前生效版本发起换版"
        items, errors = _normalize_items(values.get("items")) if values.get("items") is not None else (list(entry.get("items", [])), [])
        if errors:
            return None, "；".join(errors)
        version = str(values.get("版本号") or "").strip() or _next_version(str(entry.get("版本号", "")))
        rows = store.rows(MODULE)
        if any(row.get("模板编号") == entry.get("模板编号") and row.get("版本号") == version for row in rows):
            return None, f"版本号 {version} 已存在，请换一个版本号"
        new_entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        new_entry["模板编号"] = entry.get("模板编号")
        new_entry["模板名称"] = str(values.get("模板名称") or "").strip() or entry.get("模板名称")
        new_entry["版本号"] = version
        new_entry["生效日期"] = date.today().isoformat()
        new_entry["模板状态"] = STATUS_ACTIVE
        new_entry["status"] = STATUS_ACTIVE
        new_entry["pending"] = False
        new_entry["abnormal"] = False
        new_entry["items"] = items
        rows.append(new_entry)
        # 旧版只保留查看：状态置为已停用，不再允许套用与换版
        entry["status"] = STATUS_RETIRED
        entry["模板状态"] = STATUS_RETIRED
        return {**new_entry, "条目数": len(items)}, f"模板已换版为 {version}，旧版 {entry.get('版本号')} 仅保留查看"

    def apply_template(
        self,
        entry_id: int,
        *,
        task: str | None = None,
        entry_ids: list[int] | None = None,
    ) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]], str]:
        """把生效中的模板套到待验收单据上，返回（是否受理, 成功列表, 失败列表, 说明）。"""
        template = store.find(MODULE, entry_id)
        if template is None:
            return False, [], [], f"模板 {entry_id} 不存在或已归档"
        if template.get("status") != STATUS_ACTIVE:
            return False, [], [], f"模板 {template.get('模板编号')} {template.get('版本号')} 已停用，仅保留查看，不能套用"
        candidates: list[dict[str, Any]] = []
        if entry_ids:
            for verify_id in entry_ids:
                row = store.find(VERIFY_MODULE, int(verify_id))
                if row is not None:
                    candidates.append(row)
        else:
            candidates = [
                row for row in store.rows(VERIFY_MODULE)
                if row.get("status") == APPLIABLE_STATUS
                and (not task or str(row.get("关联任务", "")) == task)
            ]
        if not candidates:
            scope = f"关联任务 {task} 下" if task else ""
            return True, [], [], f"{scope}没有可套用的待验收单据"
        applied: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for row in candidates:
            ok, missing_kind, reason = self._apply_to_entry(template, row)
            if ok:
                self._failures.pop(int(row.get("id", 0)), None)
                applied.append(row)
            else:
                failure = self._record_failure(template, row, missing_kind, reason)
                failed.append(failure)
        message = f"套用完成：成功 {len(applied)} 条，失败 {len(failed)} 条"
        if failed:
            message += "，失败条目已在失败面板列出"
        return True, applied, failed, message

    def list_failures(self) -> list[dict[str, Any]]:
        return sorted(self._failures.values(), key=lambda item: int(item.get("验收单id", 0)))

    def retry_failures(
        self,
        entry_ids: list[int] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        """改完数据后重试：按失败记录里的模板编号找到当前生效版本重新套用。"""
        ids = [int(item) for item in entry_ids] if entry_ids else list(self._failures)
        if not ids:
            return [], [], "失败面板为空，没有需要重试的条目"
        applied: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for verify_id in ids:
            failure = self._failures.get(verify_id)
            row = store.find(VERIFY_MODULE, verify_id)
            if row is None:
                self._failures.pop(verify_id, None)
                continue
            template = self._active_version(str((failure or {}).get("模板编号", "")))
            if template is None:
                failure = self._record_failure(None, row, "模板版本", "模板当前无生效版本，请先换版或重新登记")
                failed.append(failure)
                continue
            ok, missing_kind, reason = self._apply_to_entry(template, row)
            if ok:
                self._failures.pop(verify_id, None)
                applied.append(row)
            else:
                failure = self._record_failure(template, row, missing_kind, reason)
                failed.append(failure)
        message = f"重试完成：成功 {len(applied)} 条，仍失败 {len(failed)} 条"
        return applied, failed, message

    def _active_version(self, code: str) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if row.get("模板编号") == code and row.get("status") == STATUS_ACTIVE:
                return row
        return None

    def _apply_to_entry(
        self,
        template: dict[str, Any],
        row: dict[str, Any],
    ) -> tuple[bool, str, str]:
        """套用单条验收单；失败时说明缺的是设备编号还是验收项目。"""
        status = str(row.get("status", ""))
        if status == "需返工":
            return False, "单据状态", "已下发返工，模板里的验收标准不可覆盖该单据"
        if status != APPLIABLE_STATUS:
            return False, "单据状态", f"当前状态为「{status}」，仅待验收单据可套用模板"
        device = str(row.get("设备编号") or "").strip()
        if not device:
            return False, "设备编号", "验收单未填写设备编号，无法匹配模板条目"
        item_name = str(row.get("验收项目") or "").strip()
        if not item_name:
            return False, "验收项目", "验收单未填写验收项目，无法匹配模板条目"
        items = template.get("items", [])
        device_items = [item for item in items if item.get("设备编号") == device]
        if not device_items:
            return False, "设备编号", f"模板 {template.get('版本号')} 中没有设备编号 {device} 的验收条目"
        matched = next((item for item in device_items if item.get("验收项目") == item_name), None)
        if matched is None:
            return False, "验收项目", f"模板 {template.get('版本号')} 中设备 {device} 缺少验收项目「{item_name}」"
        # 标准与结论建议来自同一条模板条目，保证列表里两者对得上
        row["验收标准"] = matched["验收标准"]
        row["验收结论"] = matched["结论建议"]
        row["模板编号"] = template.get("模板编号")
        row["模板版本"] = template.get("版本号")
        return True, "", ""

    def _record_failure(
        self,
        template: dict[str, Any] | None,
        row: dict[str, Any],
        missing_kind: str,
        reason: str,
    ) -> dict[str, Any]:
        failure = {
            "验收单id": int(row.get("id", 0)),
            "验收单号": row.get("验收单号", ""),
            "关联任务": row.get("关联任务", ""),
            "设备编号": row.get("设备编号", ""),
            "验收项目": row.get("验收项目", ""),
            "缺失项": missing_kind,
            "原因说明": reason,
            "模板编号": (template or {}).get("模板编号", ""),
            "模板版本": (template or {}).get("版本号", ""),
            "记录时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._failures[failure["验收单id"]] = failure
        return failure
