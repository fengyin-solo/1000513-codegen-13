"""验收项目模板业务规则：模板版本管理与「按任务套用到待验收单据」。

套用采用快照语义：模板内容在套用时复制进验收单，之后模板换版、条目修改都不会
影响已经下发返工的单据，保证返工单据的验收标准不被新版本覆盖。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

TEMPLATE_MODULE = "verify_template"
FAILURE_MODULE = "verify_apply_failure"
VERIFY_MODULE = "verify"
TASK_MODULE = "task"
DEVICE_MODULES = ("signal", "switch", "track", "interlock", "atp")
ACTIVE_STATUS = "生效中"
RETIRED_STATUS = "已停用"


class TemplateService:
    # ---------- 模板维护 ----------
    def list_templates(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(TEMPLATE_MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("模板名称", ""))]
        if status:
            rows = [row for row in rows if row.get("状态") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_template(self, template_id: int) -> dict[str, Any] | None:
        return store.find(TEMPLATE_MODULE, template_id)

    def create_template(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [name for name in ("模板名称", "版本号") if not str(values.get(name) or "").strip()]
        items = self._clean_items(values.get("items"))
        if not items:
            missing.append("验收项目")
        if missing:
            return None, missing
        rows = store.rows(TEMPLATE_MODULE)
        name = str(values["模板名称"]).strip()
        version = str(values["版本号"]).strip()
        if any(row.get("模板名称") == name and row.get("版本号") == version for row in rows):
            return None, ["版本号已存在"]
        template = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "模板名称": name,
            "版本号": version,
            "适用任务": str(values.get("适用任务") or "").strip(),
            "状态": "待生效",
            "生效日期": "",
            "items": items,
        }
        rows.append(template)
        return template, []

    def activate_template(self, template_id: int) -> tuple[dict[str, Any] | None, str]:
        """新版生效：同名模板同时只允许一个生效版本，旧版自动转「已停用」只读。"""
        template = store.find(TEMPLATE_MODULE, template_id)
        if template is None:
            return None, f"模板 {template_id} 不存在"
        if template["状态"] == RETIRED_STATUS:
            return None, "已停用版本仅供查看，不能重新生效，请基于它创建新版"
        for row in store.rows(TEMPLATE_MODULE):
            if row.get("模板名称") == template["模板名称"] and row["id"] != template_id:
                row["状态"] = RETIRED_STATUS
                row["生效日期"] = row.get("生效日期") or ""
        template["状态"] = ACTIVE_STATUS
        template["生效日期"] = datetime.now().strftime("%Y-%m-%d")
        return template, f"模板 {template['模板名称']}/{template['版本号']} 已生效，同名旧版已停用"

    def update_template(self, template_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """生效模板的标准内容不可改（防止返工单据口径被覆盖）；只允许改关联任务。"""
        template = store.find(TEMPLATE_MODULE, template_id)
        if template is None:
            return None, f"模板 {template_id} 不存在"
        if template["状态"] == RETIRED_STATUS:
            return None, "旧版模板只保留查看，不能修改；需要调整请创建新版"
        if "items" in values:
            return None, "模板已生效，验收项目与标准不允许修改；标准变更请换版"
        if values.get("适用任务") is not None:
            template["适用任务"] = str(values.get("适用任务") or "").strip()
        return template, "模板关联任务已更新"

    # ---------- 套用 ----------
    def apply_template(
        self,
        template_id: int,
        task_code: str,
    ) -> tuple[dict[str, Any] | None, str]:
        template = store.find(TEMPLATE_MODULE, template_id)
        if template is None:
            return None, f"模板 {template_id} 不存在"
        if template["状态"] != ACTIVE_STATUS:
            return None, f"模板版本 {template['版本号']} 不是生效版本，不能套用"
        task_code = str(task_code or "").strip()
        if not task_code:
            return None, "请指定关联任务"
        task = self._find_task(task_code)
        if task is None:
            return None, f"关联任务 {task_code} 不存在"
        if str(task.get("status") or "") != "待验收":
            return None, f"任务 {task_code} 当前状态为「{task.get('status')}」，仅待验收任务可套用模板"
        scoped = str(template.get("适用任务") or "")
        scoped_tasks = [part.strip() for part in scoped.replace("，", "、").split("、") if part.strip()]
        if scoped_tasks and task_code not in scoped_tasks:
            return None, (f"模板 {template['模板名称']}/{template['版本号']} 的关联任务为"
                          f"「{scoped}」，不包含 {task_code}，请在模板页调整关联任务后再套用")

        device_codes = self._task_devices(task)
        device_category = self._device_category_map()
        known_devices = set(device_category)
        version_tag = f"{template['模板名称']}/{template['版本号']}"
        applied: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        verify_rows = store.rows(VERIFY_MODULE)

        for item in template["items"]:
            if not item.get("验收项目"):
                continue
            category = str(item.get("适用设备类别") or "").strip()
            target_devices = [
                code for code in device_codes
                if not category or device_category.get(code) == category
            ]
            for device in target_devices:
                missing: list[str] = []
                if device and device not in known_devices:
                    missing.append("设备编号缺失")
                exists = any(
                    row.get("关联任务") == task_code
                    and row.get("设备编号") == device
                    and row.get("验收项目") == item["验收项目"]
                    and row.get("模板版本") == version_tag
                    for row in verify_rows
                )
                if exists:
                    continue
                if missing:
                    failures.append(self._record_failure(task_code, device, item, version_tag, missing))
                    continue
                entry = {
                    "id": max((int(row.get("id", 0)) for row in verify_rows), default=0) + 1,
                    "验收单号": self._next_entry_no(verify_rows),
                    "关联任务": task_code,
                    "设备编号": device,
                    "验收项目": item["验收项目"],
                    "验收标准": item.get("验收标准", ""),
                    "验收结论": "",
                    "结论建议": item.get("结论建议", ""),
                    "验收人员": "",
                    "验收日期": "",
                    "模板版本": version_tag,
                    "status": "待验收",
                    "pending": True,
                    "abnormal": False,
                }
                verify_rows.append(entry)
                applied.append(entry)

        summary = {
            "套用成功": len(applied),
            "套用失败": len(failures),
            "applied": applied,
            "failures": failures,
        }
        if not applied and failures:
            return summary, "全部条目套用失败，请在失败面板修正后重试"
        if failures:
            return summary, f"成功套用 {len(applied)} 条，{len(failures)} 条失败，已列入失败面板"
        return summary, f"已按任务 {task_code} 套用 {len(applied)} 条验收项目"

    def list_failures(
        self,
        *,
        keyword: str | None = None,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = store.rows(FAILURE_MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("验收单", ""))
                    or keyword in str(row.get("关联任务", ""))
                    or keyword in str(row.get("设备编号", ""))]
        if kind:
            rows = [row for row in rows if row.get("缺失类型") == kind]
        if status:
            rows = [row for row in rows if row.get("状态") == status]
        return rows

    def retry_failure(self, failure_id: int) -> tuple[dict[str, Any] | None, str]:
        """改完数据后重试单条失败：重新校验设备编号与模板验收项目，通过即补建验收单。"""
        failure = store.find(FAILURE_MODULE, failure_id)
        if failure is None:
            return None, f"失败记录 {failure_id} 不存在或已清除"
        template_name, _, version = str(failure.get("模板版本", "")).partition("/")
        template = next(
            (row for row in store.rows(TEMPLATE_MODULE)
             if row.get("模板名称") == template_name and row.get("版本号") == version),
            None,
        )
        if template is None:
            return None, "原模板版本已不存在，无法重试"
        item = next((it for it in template.get("items", [])
                     if it.get("验收项目") == failure.get("验收项目")), None)
        device_category = self._device_category_map()
        device_code = str(failure.get("设备编号") or "")
        if device_code and device_code not in device_category:
            failure["重试次数"] = int(failure.get("重试次数", 0)) + 1
            failure["最近尝试时间"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            return None, f"设备编号 {device_code} 仍未登记，请补登设备后再重试"
        category = str((item or {}).get("适用设备类别") or "")
        if device_code and category and device_category.get(device_code) != category:
            failure["重试次数"] = int(failure.get("重试次数", 0)) + 1
            failure["最近尝试时间"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            return None, f"设备 {device_code} 不属于该模板要求的设备类别，请核对编号"
        if item is None:
            failure["状态"] = "已放弃"
            return None, "新版模板中已没有该验收项目，请在模板页确认后重新套用"

        verify_rows = store.rows(VERIFY_MODULE)
        entry = {
            "id": max((int(row.get("id", 0)) for row in verify_rows), default=0) + 1,
            "验收单号": str(failure.get("验收单") or self._next_entry_no(verify_rows)),
            "关联任务": failure.get("关联任务", ""),
            "设备编号": failure.get("设备编号", ""),
            "验收项目": item["验收项目"],
            "验收标准": item.get("验收标准", ""),
            "验收结论": "",
            "结论建议": item.get("结论建议", ""),
            "验收人员": "",
            "验收日期": "",
            "模板版本": failure.get("模板版本", ""),
            "status": "待验收",
            "pending": True,
            "abnormal": False,
        }
        verify_rows.append(entry)
        store.rows(FAILURE_MODULE).remove(failure)
        return entry, f"重试成功，已补建验收单 {entry['验收单号']}"

    def dismiss_failure(self, failure_id: int) -> tuple[bool, str]:
        failure = store.find(FAILURE_MODULE, failure_id)
        if failure is None:
            return False, f"失败记录 {failure_id} 不存在"
        store.rows(FAILURE_MODULE).remove(failure)
        return True, "失败记录已清除"

    # ---------- 私有辅助 ----------
    def _clean_items(self, raw: Any) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        if not isinstance(raw, list):
            return items
        for raw_item in raw:
            if not isinstance(raw_item, dict):
                continue
            name = str(raw_item.get("验收项目") or "").strip()
            if not name:
                continue
            if any(item["验收项目"] == name for item in items):
                continue
            items.append({
                "验收项目": name,
                "适用设备类别": str(raw_item.get("适用设备类别") or "").strip(),
                "验收标准": str(raw_item.get("验收标准") or "").strip(),
                "结论建议": str(raw_item.get("结论建议") or "建议通过").strip() or "建议通过",
            })
        return items

    def _find_task(self, task_code: str) -> dict[str, Any] | None:
        return next((row for row in store.rows(TASK_MODULE)
                     if str(row.get("任务编号")) == task_code), None)

    def _task_devices(self, task: dict[str, Any]) -> list[str]:
        raw = str(task.get("涉及设备") or "")
        return [part.strip() for part in raw.replace("，", "、").split("、") if part.strip()]

    def _device_category_map(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for module in DEVICE_MODULES:
            for row in store.rows(module):
                code = str(row.get("设备编号") or "").strip()
                if code:
                    mapping[code] = module
        return mapping

    def _record_failure(
        self,
        task_code: str,
        device: str,
        item: dict[str, Any],
        version_tag: str,
        _missing: list[str],
    ) -> dict[str, Any]:
        rows = store.rows(FAILURE_MODULE)
        failure = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "验收单": "",
            "关联任务": task_code,
            "设备编号": device,
            "验收项目": item.get("验收项目", ""),
            "缺失类型": "设备编号缺失",
            "缺失说明": f"设备台账中查不到编号 {device}，请先补登设备或修正编号",
            "模板版本": version_tag,
            "最近尝试时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "重试次数": 0,
            "状态": "待修正",
        }
        rows.append(failure)
        return failure

    def _next_entry_no(self, verify_rows: list[dict[str, Any]]) -> str:
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"VERI-{today}-"
        seq = 0
        for row in verify_rows:
            code = str(row.get("验收单号") or "")
            if code.startswith(prefix):
                try:
                    seq = max(seq, int(code.rsplit("-", 1)[-1]))
                except ValueError:
                    continue
        return f"{prefix}{seq + 1:02d}"


template_service = TemplateService()
