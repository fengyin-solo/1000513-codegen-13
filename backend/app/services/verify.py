"""验收确认业务规则：状态流转、字段校验、返工保护与交付清单口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "verify"
REQUIRED_FIELDS = ["验收单号", "关联任务", "验收项目"]
STATUS_ORDER = ["待验收", "验收中", "已通过", "需返工"]
# 动作目标状态沿用原口径；「返修复检」用于返工单据整改完成后重新进入验收。
ACTION_RULES = {"开始验收": "验收中", "确认通过": "已通过", "下发返工": "需返工", "返修复检": "验收中"}
NEGATIVE_ACTIONS = ["下发返工"]
LIST_FIELDS = ["验收单号", "关联任务", "设备编号", "验收项目", "验收标准",
               "验收结论", "结论建议", "验收人员", "验收日期", "模板版本", "验收状态"]


class VerifyService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        task: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("验收单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if task:
            rows = [row for row in rows if task in str(row.get("关联任务", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def stats(self) -> dict[str, int]:
        rows = store.rows(MODULE)
        return {
            "待验收单据": sum(1 for row in rows if row.get("status") == "待验收"),
            "验收中单据": sum(1 for row in rows if row.get("status") == "验收中"),
            "已通过单据": sum(1 for row in rows if row.get("status") == "已通过"),
            "需返工项数": sum(1 for row in rows if row.get("status") == "需返工"),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in ("设备编号", "验收标准", "验收结论", "结论建议", "验收人员", "验收日期", "模板版本"):
            entry[field] = values.get(field, "")
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"验收单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于验收确认可执行范围"
        target = ACTION_RULES[action]

        # 状态守卫沿用老流程：只有进行中的单子能确认通过 / 下发返工。
        current = str(entry.get("status") or "")
        if action == "开始验收" and current != "待验收":
            return None, "仅待验收单据可以开始验收"
        if action in ("确认通过", "下发返工") and current != "验收中":
            return None, f"单据当前为「{current}」，需先开始验收再{action}"
        if action == "返修复检" and current != "需返工":
            return None, "仅需返工单据整改完成后可以申请复检"

        entry["status"] = target
        entry["pending"] = target not in ("已通过",)
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        # 下发返工只改状态，验收标准/结论原样保留，模板口径绝不被覆盖。
        if action == "确认通过":
            entry["验收结论"] = entry.get("验收结论") or entry.get("结论建议") or "符合验收标准，同意通过"
            if not entry.get("结论建议"):
                entry["结论建议"] = "建议通过"
        return entry, f"验收单已{action}"

    def delivery_items(self) -> list[dict[str, Any]]:
        """交付清单只取「确认通过」的单据；结论与标准成对列出，便于现场核对。"""
        return [
            {
                "验收单号": row.get("验收单号", ""),
                "关联任务": row.get("关联任务", ""),
                "设备编号": row.get("设备编号", ""),
                "验收项目": row.get("验收项目", ""),
                "验收标准": row.get("验收标准", ""),
                "验收结论": row.get("验收结论", ""),
                "验收人员": row.get("验收人员", ""),
                "验收日期": row.get("验收日期", ""),
                "模板版本": row.get("模板版本", ""),
            }
            for row in store.rows(MODULE)
            if row.get("status") == "已通过"
        ]
