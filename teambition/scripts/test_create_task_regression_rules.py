"""create_task 回归脚本：项目强校验、备注模板、开发人天默认与告警"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from teambition_mcp_server import (
    ORG_ID,
    _ensure_logged_in,
    _get_client,
    _retry_request,
    create_task,
    delete_task,
    list_tasks,
)

WUFN_PROJECT_ID = "693907787ad8b6f61a76a0a6"


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"返回值不是JSON: {raw}") from exc


def _get_task_detail(task_id: str) -> dict:
    _ensure_logged_in()
    client = _get_client()
    resp = _retry_request(
        lambda: client.get(
            f"/api/tasks/{task_id}",
            headers={"X-Tenant-Id": ORG_ID},
        )
    )
    return resp.json()


def _cleanup(task_id: str | None) -> None:
    if not task_id:
        return
    print(f"  清理任务: {task_id}")
    print(f"  删除结果: {delete_task(task_id=task_id, project_id=WUFN_PROJECT_ID)}")


def test_project_required() -> None:
    print("[1/4] 校验：未指定项目ID时禁止任务操作")

    create_result = create_task(project_id="", content="[回归] 项目必填")
    assert "未指定任务所属项目" in create_result, create_result

    list_result = list_tasks(project_id="")
    assert "未指定任务所属项目" in list_result, list_result

    print("  [PASS] 通过")


def test_note_and_default_dev_days() -> None:
    print("[2/4] 校验：备注三段结构 + 开发人天默认1")
    task_id = None
    try:
        raw = create_task(
            project_id=WUFN_PROJECT_ID,
            content=f"[回归] 默认开发人天-{int(time.time())}",
            note="仅有一段简短备注",
        )
        data = _parse_json(raw)
        assert data.get("status") == "success", raw
        assert data.get("devDays") == "1", data
        assert data.get("devDaysFieldUpdated") is True, data

        task_id = data.get("_id")
        detail = _get_task_detail(task_id)
        note_text = detail.get("note", "")

        assert "问题现象" in note_text, note_text
        assert "可能原因" in note_text, note_text
        assert "需要验证" in note_text, note_text

        print("  [PASS] 通过")
    finally:
        _cleanup(task_id)


def test_invalid_dev_days_warning() -> None:
    print("[3/4] 校验：dev_days 非法值告警并回退1")
    task_id = None
    try:
        raw = create_task(
            project_id=WUFN_PROJECT_ID,
            content=f"[回归] 非法开发人天-{int(time.time())}",
            dev_days=-3,
        )
        data = _parse_json(raw)
        assert data.get("status") == "success", raw
        assert data.get("devDays") == "1", data

        warnings = data.get("warnings", [])
        assert warnings, data
        assert any("已强制回退为1" in w for w in warnings), data

        task_id = data.get("_id")
        print("  [PASS] 通过")
    finally:
        _cleanup(task_id)


def test_template_note_params() -> None:
    print("[4/4] 校验：模板化备注参数（现象/原因/验证）")
    task_id = None
    try:
        raw = create_task(
            project_id=WUFN_PROJECT_ID,
            content=f"[回归] 模板备注-{int(time.time())}",
            issue_phenomenon="发票ERS-30-03-26-4914无法重新验证",
            possible_reason="疑似部分行未入账、部分行已入账导致状态不一致",
            verification_items="1. 核对每行入账状态\n2. 校验重新验证规则",
            note="补充：请优先排查最近一次状态变更日志",
        )
        data = _parse_json(raw)
        assert data.get("status") == "success", raw
        task_id = data.get("_id")

        detail = _get_task_detail(task_id)
        note_text = detail.get("note", "")

        assert "【问题现象】" in note_text, note_text
        assert "【可能原因】" in note_text, note_text
        assert "【需要验证】" in note_text, note_text
        assert "【补充说明】" in note_text, note_text
        assert "部分行未入账" in note_text, note_text

        print("  [PASS] 通过")
    finally:
        _cleanup(task_id)


def run_all() -> None:
    # @Description
    #   v1.1 2026-04-08 10:35:00 控制台输出统一为ASCII，避免Windows GBK环境下emoji编码失败
    # @Author echizen_hua
    # @Date 2026-04-08 10:35:00
    print("=" * 72)
    print("create_task 回归脚本：项目强校验 + 备注模板 + 开发人天默认")
    print("=" * 72)

    test_project_required()
    test_note_and_default_dev_days()
    test_invalid_dev_days_warning()
    test_template_note_params()

    print("\n[PASS] 全部回归校验通过")


if __name__ == "__main__":
    run_all()
