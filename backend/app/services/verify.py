"""验收确认业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "verify"
REQUIRED_FIELDS = ["验收单号", "关联任务", "验收项目"]
STATUS_ORDER = ["待验收", "验收中", "已通过", "需返工"]
ACTION_RULES = {"开始验收": "验收中", "确认通过": "已通过", "下发返工": "需返工"}
NEGATIVE_ACTIONS = []
EDITABLE_FIELDS = ["关联任务", "设备编号", "验收项目", "验收标准", "验收结论", "验收人员", "验收日期"]
# 进入这些状态后，验收标准与验收结论锁定，不允许再被改动或覆盖
LOCKED_STATUSES = {
    "需返工": "已下发返工，模板带出的验收标准不可被覆盖",
    "已通过": "验收单已通过，验收标准与验收结论不可再修改",
}
DELIVERY_FIELDS = ["验收单号", "关联任务", "设备编号", "验收项目", "验收标准", "验收结论", "验收人员", "验收日期"]


class VerifyService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        task: str | None = None,
        device: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("验收单号", ""))]
        if task:
            rows = [row for row in rows if task in str(row.get("关联任务", ""))]
        if device:
            rows = [row for row in rows if device in str(row.get("设备编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["设备编号"] = str(values.get("设备编号") or "").strip()
        entry["验收标准"] = ""
        entry["验收结论"] = ""
        entry["status"] = STATUS_ORDER[0]
        entry["验收状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """修改验收单字段；返工或已通过的单据不允许改动验收标准与验收结论。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"验收单 {entry_id} 不存在或已归档"
        updates = {field: values[field] for field in EDITABLE_FIELDS if field in values}
        if not updates:
            return None, "没有可更新的字段，请先修改内容再提交"
        lock_message = LOCKED_STATUSES.get(str(entry.get("status", "")))
        if lock_message:
            changed_locked = [
                field for field in ("验收标准", "验收结论")
                if field in updates and str(updates[field]) != str(entry.get(field, ""))
            ]
            if changed_locked:
                return None, lock_message
        note = ""
        # 验收标准变更后，旧结论与新标准对不上：同步清空结论，提醒重新填写
        if (
            "验收标准" in updates
            and "验收结论" not in updates
            and str(updates["验收标准"]) != str(entry.get("验收标准", ""))
        ):
            entry["验收结论"] = ""
            note = "；验收标准已变更，验收结论已清空，请重新填写"
        for field, value in updates.items():
            entry[field] = value
        return entry, f"验收单已更新{note}"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"验收单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于验收确认可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["验收状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"验收单已{action}"

    def delivery_entries(self) -> list[dict[str, Any]]:
        """交付清单：只取确认通过的验收单，结论与标准以单据上锁定的内容为准。"""
        rows = [row for row in store.rows(MODULE) if row.get("status") == "已通过"]
        return [{field: row.get(field, "") for field in DELIVERY_FIELDS} for row in rows]
