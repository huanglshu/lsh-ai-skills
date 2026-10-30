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

    def run_summary(self, repo=None, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(repo or self.repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_unstaged_and_untracked_changes_from_subdirectory(self):
        (self.repo / "tracked.txt").write_text("after\n", encoding="utf-8")
        (self.repo / "deleted.txt").unlink()
        (self.repo / "new.txt").write_text("new\n", encoding="utf-8")
        subdir = self.repo / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested\n", encoding="utf-8")

        result = self.run_summary(subdir)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")
        for name in ("tracked.txt", "deleted.txt", "new.txt", "subdir/nested.txt"):
            self.assertIn(name, result.stdout)
        self.assertIn("未暂存", result.stdout)
        self.assertIn("未跟踪", result.stdout)

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
        self.assertIn("已暂存", result.stdout)
        self.assertIn("未暂存", result.stdout)
        self.assertIn("new.txt", result.stdout)
        self.assertEqual(result.stdout.count("`tracked.txt`"), 2)

    def test_ignored_files_are_excluded_but_tracked_files_are_kept(self):
        (self.repo / ".gitignore").write_text("*.txt\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("after\n", encoding="utf-8")
        (self.repo / "ignored.txt").write_text("secret\n", encoding="utf-8")
        (self.repo / "visible.py").write_text("def visible():\n    pass\n", encoding="utf-8")

        result = self.run_summary()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tracked.txt", result.stdout)
        self.assertIn("visible.py", result.stdout)
        self.assertIn("visible()", result.stdout)
        self.assertNotIn("ignored.txt", result.stdout)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")

    def test_staged_only_ignores_other_changes(self):
        (self.repo / "tracked.txt").write_text("staged\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        (self.repo / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
        (self.repo / "new.txt").write_text("new\n", encoding="utf-8")

        result = self.run_summary(None, "--staged-only")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tracked.txt", result.stdout)
        self.assertNotIn("new.txt", result.stdout)
        self.assertNotIn("未暂存变更", result.stdout)
        self.assertEqual(self.git("show", ":tracked.txt"), "staged\n")

    def test_unicode_paths_binary_and_empty_untracked_file(self):
        (self.repo / "中文 文件.py").write_text("def example():\n    pass\n", encoding="utf-8")
        (self.repo / "image.bin").write_bytes(b"\0binary")
        (self.repo / "empty.txt").write_text("", encoding="utf-8")

        result = self.run_summary()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("中文 文件.py", result.stdout)
        self.assertIn("example()", result.stdout)
        self.assertIn("image.bin", result.stdout)
        self.assertIn("二进制", result.stdout)
        self.assertIn("empty.txt", result.stdout)

    def test_staged_rename_and_unstaged_edit_are_separate(self):
        self.git("mv", "tracked.txt", "重命名.txt")
        (self.repo / "重命名.txt").write_text("after\n", encoding="utf-8")

        result = self.run_summary()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("重命名", result.stdout)
        self.assertEqual(result.stdout.count("`重命名.txt`"), 2)
        self.assertIn("tracked.txt -> 重命名.txt", result.stdout)
        self.assertEqual(self.git("show", ":重命名.txt"), "before\n")

    def test_repository_without_first_commit(self):
        fresh = self.repo / "fresh"
        fresh.mkdir()
        subprocess.run(["git", "-C", str(fresh), "init", "-q"], check=True)
        (fresh / "new.py").write_text("def created():\n    pass\n", encoding="utf-8")

        result = self.run_summary(fresh)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("new.py", result.stdout)
        self.assertIn("created()", result.stdout)
        status = subprocess.run(
            ["git", "-C", str(fresh), "status", "--porcelain"],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn("?? new.py", status)

    def test_clean_repo_reports_no_changes(self):
        result = self.run_summary()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("未检测到 Git 变更", result.stdout)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")


if __name__ == "__main__":
    unittest.main()
