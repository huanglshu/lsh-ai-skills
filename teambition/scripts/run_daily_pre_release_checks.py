"""发布前检查入口：建议每日执行，至少执行 create_task 回归规则集。"""

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def run_case(script_name: str) -> tuple[bool, str]:
    script_path = BASE_DIR / script_name
    cmd = [sys.executable, str(script_path)]
    print(f"\n[RUN] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("[STDERR]")
        print(result.stderr)

    return result.returncode == 0, script_name


def main() -> int:
    print("=" * 72)
    print("Teambition 发布前检查（建议最少每日一次）")
    print("=" * 72)

    cases = [
        "test_create_task_regression_rules.py",
    ]

    passed = []
    failed = []
    for case in cases:
        ok, name = run_case(case)
        if ok:
            passed.append(name)
        else:
            failed.append(name)

    print("\n" + "=" * 72)
    print(f"通过: {len(passed)} | 失败: {len(failed)}")
    if passed:
        print("通过项:")
        for item in passed:
            print(f"- {item}")
    if failed:
        print("失败项:")
        for item in failed:
            print(f"- {item}")
    print("=" * 72)

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
