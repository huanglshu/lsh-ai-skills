import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_staged_summary.py"


class StagedSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.repo = Path(self.temp_dir.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        (self.repo / "tracked.txt").write_text("before\n", encoding="utf-8")
        (self.repo / "deleted.txt").write_text("before\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-qm", "initial")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout

    def run_summary(self, repo=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(repo or self.repo)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_empty_index_stages_all_changes_from_subdirectory(self):
        (self.repo / "tracked.txt").write_text("after\n", encoding="utf-8")
        (self.repo / "deleted.txt").unlink()
        (self.repo / "new.txt").write_text("new\n", encoding="utf-8")
        subdir = self.repo / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested\n", encoding="utf-8")

        result = self.run_summary(subdir)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("正在暂存", result.stderr)
        self.assertEqual(
            set(self.git("diff", "--cached", "--name-only").splitlines()),
            {"tracked.txt", "deleted.txt", "new.txt", "subdir/nested.txt"},
        )
        self.assertIn("影响文件：4 个", result.stdout)

    def test_existing_index_does_not_stage_other_changes(self):
        (self.repo / "tracked.txt").write_text("staged\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        (self.repo / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
        (self.repo / "new.txt").write_text("new\n", encoding="utf-8")

        result = self.run_summary()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("正在暂存", result.stderr)
        self.assertEqual(self.git("diff", "--cached", "--name-only").strip(), "tracked.txt")
        self.assertEqual(self.git("show", ":tracked.txt"), "staged\n")
        self.assertIn("影响文件：1 个", result.stdout)

    def test_clean_repo_reports_no_changes(self):
        result = self.run_summary()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("未检测到暂存区变更", result.stdout)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")


if __name__ == "__main__":
    unittest.main()
