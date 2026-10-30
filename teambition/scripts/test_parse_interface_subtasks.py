"""Regression test for interface breakdown parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parse_interface_subtasks import parse_breakdown


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    items = parse_breakdown(ROOT / "接口子任务拆解文档.md")

    assert len(items) == 25, len(items)
    assert sum(len(item["subtasks"]) for item in items) == 110
    assert items[0]["title"] == "企业组织（部门）同步"
    assert items[0]["subtasks"][0].startswith("确认部门编码")
    assert not items[0]["subtasks"][0].startswith("1.1")
    assert items[-1]["title"] == "员工合同信息查询"

    print("[PASS] interface subtask breakdown parser")


if __name__ == "__main__":
    main()
