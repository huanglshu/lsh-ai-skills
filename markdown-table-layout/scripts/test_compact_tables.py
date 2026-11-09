import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("compact_tables.py")
spec = importlib.util.spec_from_file_location("compact_tables_test", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

TABLE = (
    "| 字段 | 说明 | 类型 | 示例 | 备注 |\n"
    "| --- | :---: | --- | --- | --- |\n"
    "| `A\\|B` | **手工备注** | 文本 | [文档](../guide.md) | 需保留 |\n"
    "| 二 | 三 | 四 | 五 | 六 |\n"
)


class CompactTablesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def make_plan(self, paths, name="plan.json", recursive=False, min_columns=4):
        args = argparse.Namespace(
            inputs=[str(p) for p in paths],
            output=str(self.root / name),
            recursive=recursive,
            min_columns=min_columns,
        )
        return module.plan(args), Path(args.output)

    def test_plan_apply_preserves_current_content_and_is_idempotent(self):
        source = self.root / "客户文档.md"
        untouched = self.root / "其他.md"
        text = (
            "---\ntitle: 测试\n---\n\n# 用户新增内容\n\n"
            "| 项目 | 内容 |\n| --- | --- |\n| 姓名 | 保留 |\n\n"
            + TABLE
            + "\n```markdown\n| 不 | 是 | 真 | 表 |\n| --- | --- | --- | --- |\n```\n"
            + "\n用户追加：绝对不要丢。\n"
        )
        source.write_text(text, encoding="utf-8")
        untouched.write_text("仅保留的正文\n", encoding="utf-8")
        result, plan = self.make_plan([self.root])
        self.assertEqual(result["files"], 1)
        self.assertEqual(result["tables"], 1)
        self.assertEqual(source.read_text(encoding="utf-8"), text)
        self.assertNotIn("手工备注", plan.read_text(encoding="utf-8"))
        applied = module.apply(argparse.Namespace(plan=str(plan)))
        self.assertEqual(applied["files"], 1)
        updated = source.read_text(encoding="utf-8")
        self.assertIn("用户追加：绝对不要丢。", updated)
        self.assertIn("| 项目 | 内容 |", updated)
        self.assertIn("```markdown\n| 不 | 是 | 真 | 表 |", updated)
        self.assertIn("<strong>手工备注</strong>", updated)
        self.assertIn('href="../guide.md"', updated)
        self.assertIn("A|B", updated)
        self.assertIn("text-align:center", updated)
        self.assertEqual(untouched.read_text(encoding="utf-8"), "仅保留的正文\n")
        again, _ = self.make_plan([source], "again.json")
        self.assertEqual(again["files"], 0)

    def test_stale_plan_does_not_write_any_file(self):
        first, second = self.root / "a.md", self.root / "b.md"
        first.write_text(TABLE, encoding="utf-8")
        second.write_text(TABLE, encoding="utf-8")
        _, plan = self.make_plan([first, second])
        second.write_text(TABLE + "\n用户又做了修改\n", encoding="utf-8")
        with self.assertRaisesRegex(module.LayoutError, "changed since planning"):
            module.apply(argparse.Namespace(plan=str(plan)))
        self.assertEqual(first.read_text(encoding="utf-8"), TABLE)
        self.assertIn("用户又做了修改", second.read_text(encoding="utf-8"))

    def test_existing_plan_is_never_overwritten(self):
        source = self.root / "a.md"
        source.write_text(TABLE, encoding="utf-8")
        plan = self.root / "plan.json"
        plan.write_text("keep me", encoding="utf-8")
        with self.assertRaisesRegex(module.LayoutError, "already exists"):
            self.make_plan([source])
        self.assertEqual(plan.read_text(encoding="utf-8"), "keep me")
        self.assertEqual(source.read_text(encoding="utf-8"), TABLE)

    def test_extra_cells_and_bare_url_are_skipped(self):
        extra = self.root / "extra.md"
        extra_text = "| a | b | c | d |\n| --- | --- | --- | --- |\n| 1 | 2 | 3 | 4 | 未命名数据 |\n"
        extra.write_text(extra_text, encoding="utf-8")
        url = self.root / "url.md"
        url_text = "| a | b | c | d |\n| --- | --- | --- | --- |\n| 1 | 2 | https://example.test/x | 4 |\n"
        url.write_text(url_text, encoding="utf-8")
        result, _ = self.make_plan([extra, url])
        self.assertEqual(result["files"], 0)
        self.assertEqual(len(result["skipped"]), 2)
        self.assertEqual(extra.read_text(encoding="utf-8"), extra_text)
        self.assertEqual(url.read_text(encoding="utf-8"), url_text)

    def test_code_url_is_not_an_autolink(self):
        source = self.root / "code.md"
        source.write_text("| a | b | c | d |\n| --- | --- | --- | --- |\n| 1 | 2 | `https://example.test/x` | 4 |\n", encoding="utf-8")
        result, plan = self.make_plan([source])
        self.assertEqual(result["files"], 1)
        module.apply(argparse.Namespace(plan=str(plan)))
        self.assertIn("<code>https://example.test/x</code>", source.read_text(encoding="utf-8"))

    def test_unsafe_inline_html_is_skipped_but_line_break_is_preserved(self):
        source = self.root / "inline-html.md"
        unsafe = "| a | b | c | d |\n| --- | --- | --- | --- |\n| <HEADER> | 2 | 3 | 4 |\n"
        source.write_text(unsafe, encoding="utf-8")
        result, _ = self.make_plan([source])
        self.assertEqual(result["files"], 0)
        self.assertIn("inline HTML", result["skipped"][0]["reason"])
        self.assertEqual(source.read_text(encoding="utf-8"), unsafe)
        safe = unsafe.replace("<HEADER>", "first<br>second")
        source.write_text(safe, encoding="utf-8")
        result, plan = self.make_plan([source], "safe.json")
        self.assertEqual(result["files"], 1)
        module.apply(argparse.Namespace(plan=str(plan)))
        self.assertIn("first<br>second", source.read_text(encoding="utf-8"))

    def test_gfm_strikethrough_and_renderer_extensions(self):
        source = self.root / "extensions.md"
        text = "| a | b | c | d |\n| --- | --- | --- | --- |\n| ~~deprecated~~ | 2 | 3 | 4 |\n"
        source.write_text(text, encoding="utf-8")
        result, plan = self.make_plan([source])
        self.assertEqual(result["files"], 1)
        module.apply(argparse.Namespace(plan=str(plan)))
        self.assertIn("<s>deprecated</s>", source.read_text(encoding="utf-8"))
        for marker in ("==highlight==", ":smile:", "[^footnote]", "$x+y$", "~two words~", "^two words^"):
            candidate = self.root / ("extension-" + str(len(marker)) + "-" + str(ord(marker[0])) + ".md")
            candidate.write_text(text.replace("~~deprecated~~", marker), encoding="utf-8")
            changed, _, skipped = module.transform(candidate.read_text(encoding="utf-8"), 4)
            self.assertEqual(changed, candidate.read_text(encoding="utf-8"))
            self.assertTrue(skipped, marker)

    def test_percentage_html_with_nowrap_headers_is_not_treated_as_compact(self):
        generated, count, skipped = module.transform(TABLE, 4)
        self.assertEqual(count, 1)
        self.assertFalse(skipped)
        degraded = generated.replace("white-space: normal", "white-space: nowrap", 1)
        repaired, count, skipped = module.transform(degraded, 4)
        self.assertEqual(count, 1)
        self.assertFalse(skipped)
        self.assertNotIn("white-space: nowrap", repaired)
        self.assertEqual(module.snapshot(generated), module.snapshot(repaired))
        self.assertEqual(module.transform(repaired, 4)[0], repaired)

    def test_defined_footnote_reference_is_not_rewritten_as_a_link(self):
        source = self.root / "footnotes.md"
        text = (
            "| a | b | c | d |\n| --- | --- | --- | --- |\n"
            "| Value[^note] | 2 | 3 | 4 |\n\n[^note]: explanation\n"
        )
        source.write_text(text, encoding="utf-8")
        result, _ = self.make_plan([source])
        self.assertEqual(result["files"], 0)
        self.assertIn("footnote", result["skipped"][0]["reason"])
        self.assertEqual(source.read_text(encoding="utf-8"), text)

    def test_nested_markdown_table_is_skipped(self):
        source = self.root / "nested.md"
        text = "\n".join("> " + line for line in TABLE.splitlines()) + "\n"
        source.write_text(text, encoding="utf-8")
        result, _ = self.make_plan([source])
        self.assertEqual(result["files"], 0)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(source.read_text(encoding="utf-8"), text)

    def test_compacts_managed_html_and_preserves_cell_markup(self):
        source = self.root / "html.md"
        text = (
            '# Existing\n\n<table class="dense wide-table" style="min-width: 1200px; table-layout: fixed; width: 100%">\n'
            '<colgroup><col style="width: 300px"><col style="width: 300px">'
            '<col style="width: 300px"><col style="width: 300px"></colgroup>\n'
            '<thead><tr><th style="white-space: nowrap">字段</th><th style="white-space: nowrap">描述</th>'
            '<th style="white-space: nowrap">类型</th><th style="white-space: nowrap">说明</th></tr></thead>\n'
            '<tbody><tr><td style="word-break: break-word"><code>VALUE</code></td>'
            '<td style="word-break: break-word">用户新增 &amp; 备注</td>'
            '<td style="word-break: break-word">文本</td>'
            '<td style="word-break: break-word"><strong>保留</strong><br>换行</td></tr></tbody>\n'
            '</table>\n\n末尾正文\n'
        )
        source.write_text(text, encoding="utf-8")
        result, plan = self.make_plan([source])
        self.assertEqual(result["files"], 1)
        module.apply(argparse.Namespace(plan=str(plan)))
        updated = source.read_text(encoding="utf-8")
        self.assertEqual(module.snapshot(text), module.snapshot(updated))
        self.assertIn('min-width: 480px', updated)
        self.assertIn('overflow-x: auto', updated)
        self.assertIn('<code>VALUE</code>', updated)
        self.assertIn('末尾正文', updated)
        again, _ = self.make_plan([source], "again.json")
        self.assertEqual(again["files"], 0)

    def test_html_style_attribute_does_not_modify_other_attributes(self):
        source = self.root / "attributes.md"
        text = (
            '<table class="wide-table" data-style="user-metadata" '
            'data-note="ignore style=\'other\'" style=\'min-width: 1200px; width: 100%\'>\n'
            '<colgroup>'
            + '<col data-style="column-metadata" style="width: 300px">' * 4
            + '</colgroup><thead><tr>'
            + '<th data-style="header-metadata" style=\'white-space: nowrap\'>字段</th>' * 4
            + '</tr></thead><tbody><tr>'
            + '<td data-style="cell-metadata" style="word-break: break-word">内容</td>' * 4
            + '</tr></tbody></table>\n'
        )
        source.write_text(text, encoding="utf-8")
        result, plan = self.make_plan([source])
        self.assertEqual(result["files"], 1)
        module.apply(argparse.Namespace(plan=str(plan)))
        updated = source.read_text(encoding="utf-8")
        tree = module.MarkupTree(updated)
        tree.feed(updated)
        tree.close()
        tables = [node for node in module.walk(tree.root) if node.tag == "table"]
        self.assertEqual(tables[0].attrs["data-style"], "user-metadata")
        self.assertEqual(tables[0].attrs["data-note"], "ignore style='other'")
        self.assertEqual(module.styles(tables[0])["min-width"], "480px")
        for node in module.walk(tables[0]):
            if node.tag in {"col", "th", "td"}:
                self.assertEqual(node.attrs["data-style"], {
                    "col": "column-metadata", "th": "header-metadata", "td": "cell-metadata"
                }[node.tag])
        self.assertEqual(module.snapshot(text), module.snapshot(updated))

    def test_unmanaged_html_and_merged_cells_are_skipped(self):
        source = self.root / "unsupported.md"
        unmanaged = "<table><tr><td>保留</td></tr></table>\n\n"
        merged = (
            '<table class="wide-table" style="min-width: 800px"><colgroup>'
            + '<col style="width: 200px">' * 4
            + '</colgroup><thead><tr>'
            + '<th style="padding: 4px">x</th>' * 4
            + '</tr></thead><tbody><tr><td colspan="4" style="padding: 4px">重要</td>'
            + '</tr></tbody></table>\n'
        )
        source.write_text(unmanaged + merged, encoding="utf-8")
        result, _ = self.make_plan([source])
        self.assertEqual(result["files"], 0)
        self.assertEqual(len(result["skipped"]), 2)
        self.assertEqual(source.read_text(encoding="utf-8"), unmanaged + merged)

    def test_crlf_and_unrelated_contents_survive(self):
        source = self.root / "crlf.md"
        text = ("before\n\n" + TABLE + "\nafter\n").replace("\n", "\r\n")
        source.write_bytes(text.encode("utf-8"))
        _, plan = self.make_plan([source])
        module.apply(argparse.Namespace(plan=str(plan)))
        result = source.read_bytes()
        self.assertNotIn(b"\n", result.replace(b"\r\n", b""))
        self.assertTrue(result.startswith(b"before\r\n\r\n"))
        self.assertTrue(result.endswith(b"\r\n\r\nafter\r\n"))

    def test_cr_only_is_preserved(self):
        source = self.root / "cr.md"
        text = ("before\n\n" + TABLE + "\nafter\n").replace("\n", "\r")
        source.write_bytes(text.encode("utf-8"))
        _, plan = self.make_plan([source])
        module.apply(argparse.Namespace(plan=str(plan)))
        result = source.read_bytes()
        self.assertNotIn(b"\n", result)
        self.assertTrue(result.startswith(b"before\r\r"))
        self.assertTrue(result.endswith(b"\r\rafter\r"))

    def test_git_index_and_unstaged_changes_are_preserved(self):
        if subprocess.run(["git", "--version"], capture_output=True).returncode:
            self.skipTest("Git unavailable")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "core.autocrlf", "false"], check=True)
        source = self.root / "draft.md"
        source.write_text("# Staged\n\n" + TABLE, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "draft.md"], check=True)
        before = subprocess.check_output(["git", "-C", str(self.root), "ls-files", "--stage", "draft.md"])
        source.write_text("# Staged\n\n" + TABLE + "\n用户未暂存补充\n", encoding="utf-8")
        _, plan = self.make_plan([source])
        module.apply(argparse.Namespace(plan=str(plan)))
        after = subprocess.check_output(["git", "-C", str(self.root), "ls-files", "--stage", "draft.md"])
        self.assertEqual(before, after)
        self.assertIn("用户未暂存补充", source.read_text(encoding="utf-8"))

    def test_cli_handles_unicode_paths_on_legacy_windows_codepages(self):
        source = self.root / "文档-🍀.md"
        source.write_text(TABLE, encoding="utf-8")
        plan = self.root / "计划-🍀.json"
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "plan", str(source), "--output", str(plan)],
            capture_output=True, encoding="utf-8"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["files"], 1)
        applied = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "apply", "--plan", str(plan)],
            capture_output=True, encoding="utf-8"
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn("手工备注", source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
