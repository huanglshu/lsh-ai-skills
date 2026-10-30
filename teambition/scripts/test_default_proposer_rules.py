"""验证 create_task 的默认提出人与参与者规则（WUFN 项目）"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from teambition_mcp_server import create_task, delete_task

WUFN_PROJECT_ID = "693907787ad8b6f61a76a0a6"
CURRENT_USER_ID = "5bea5a57be825b33ab9afacb"

DEFAULT_PROPOSER = {
    "name": "古妙霞",
    "memberId": "665d864aeddf7ef85e0e4c14",
    "userId": "665d864abf5f11b187aa5279",
}


def _parse_result(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"返回值不是有效JSON: {raw}") from exc


def _cleanup_task(task_id: str | None) -> None:
    if not task_id:
        return
    print(f"  清理任务: {task_id}")
    print(f"  删除结果: {delete_task(task_id=task_id, project_id=WUFN_PROJECT_ID)}")


def test_default_proposer_and_involver() -> None:
    """集成用例：involver_ids 为空时，WUFN 默认古妙霞，且参与者同步。"""
    task_id = None
    title = f"[自动化测试] 默认提出人验证-{int(time.time())}"

    try:
        raw = create_task(
            project_id=WUFN_PROJECT_ID,
            content=title,
            executor_id=CURRENT_USER_ID,
            note="自动化集成用例：验证默认提出人和参与者同步",
            priority=0,
        )
        data = _parse_result(raw)
        assert data.get("status") == "success", f"创建失败: {raw}"

        task_id = data.get("_id")
        default_proposer = data.get("defaultProposer")

        assert default_proposer is not None, "缺少 defaultProposer 返回"
        assert default_proposer.get("name") == DEFAULT_PROPOSER["name"], (
            f"默认提出人名称不正确: {default_proposer}"
        )
        assert default_proposer.get("userId") == DEFAULT_PROPOSER["userId"], (
            f"默认提出人 userId 不正确: {default_proposer}"
        )
        assert data.get("proposerCustomFieldUpdated") is True, (
            f"WUFN 默认提出人字段未成功回填: {data}"
        )

        involvers = data.get("involvers", [])
        involver_ids = {member.get("_id") for member in involvers}
        assert DEFAULT_PROPOSER["userId"] in involver_ids, (
            f"默认提出人未加入参与者: {involvers}"
        )

        print("  ✅ 集成用例通过：默认提出人与参与者同步正确")
    finally:
        _cleanup_task(task_id)


def test_explicit_involver_no_default_override() -> None:
    """回归用例：显式传入 involver_ids 时，不应自动追加默认提出人。"""
    task_id = None
    title = f"[自动化测试] 显式参与者回归-{int(time.time())}"

    try:
        raw = create_task(
            project_id=WUFN_PROJECT_ID,
            content=title,
            executor_id=CURRENT_USER_ID,
            note="自动化回归用例：显式参与者不应被默认规则覆盖",
            priority=0,
            involver_ids=CURRENT_USER_ID,
        )
        data = _parse_result(raw)
        assert data.get("status") == "success", f"创建失败: {raw}"

        task_id = data.get("_id")
        assert "defaultProposer" not in data, (
            f"显式传入 involver_ids 时不应返回 defaultProposer: {data}"
        )

        involvers = data.get("involvers", [])
        involver_ids = {member.get("_id") for member in involvers}

        assert DEFAULT_PROPOSER["userId"] not in involver_ids, (
            f"显式参与者场景被错误追加默认提出人: {involvers}"
        )

        print("  ✅ 回归用例通过：显式参与者未被默认规则覆盖")
    finally:
        _cleanup_task(task_id)


def run_all() -> None:
    print("=" * 70)
    print("create_task 默认提出人规则自动化测试（WUFN）")
    print("=" * 70)

    print("\n[1/2] 集成用例：involver_ids 为空 -> 默认提出人+参与者同步")
    test_default_proposer_and_involver()

    print("\n[2/2] 回归用例：显式 involver_ids -> 不覆盖")
    test_explicit_involver_no_default_override()

    print("\n🎉 两类测试全部通过")


if __name__ == "__main__":
    run_all()
