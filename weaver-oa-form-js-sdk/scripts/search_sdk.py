#!/usr/bin/env python3
import argparse
import os
import re
import sys


# 按优先级查找 SDK 文档：环境变量 > 相对路径（分发包） > 绝对路径（本地开发）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_RELATIVE_SDK_PATH = os.path.join(_SCRIPT_DIR, "..", "sdk-doc", "泛微在线文档前端SDK.html")
_LOCAL_SDK_PATH = "/Users/caizhijian/aofei/泛微技术资料/泛微在线文档前端SDK.html"

def _resolve_sdk_path():
    paths = [
        os.environ.get("WEAVER_OA_SDK_HTML"),
        os.path.normpath(_RELATIVE_SDK_PATH),
        _LOCAL_SDK_PATH,
    ]
    for p in paths:
        if p and os.path.exists(p):
            return p
    return _RELATIVE_SDK_PATH  # 返回相对路径，便于报错定位

DEFAULT_SDK_PATH = _resolve_sdk_path()


def load_lines(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.readlines()


def search(lines, keywords, context):
    matches = []
    for idx, line in enumerate(lines):
        normalized = line.lower()
        if all(keyword.lower() in normalized for keyword in keywords):
            start = max(0, idx - context)
            end = min(len(lines), idx + context + 1)
            snippet = "".join(lines[start:end]).strip()
            matches.append((idx + 1, snippet))
    return matches


def strip_html(text):
    text = re.sub(r"<br\\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def main():
    parser = argparse.ArgumentParser(description="检索泛微 OA 表单前端 SDK HTML")
    parser.add_argument("keywords", nargs="+", help="检索关键词")
    parser.add_argument("--sdk-path", default=os.environ.get("WEAVER_OA_SDK_HTML", DEFAULT_SDK_PATH))
    parser.add_argument("--context", type=int, default=4, help="上下文行数")
    parser.add_argument("--max-results", type=int, default=8, help="最多返回结果数")
    parser.add_argument("--raw", action="store_true", help="输出原始 HTML 片段")
    args = parser.parse_args()

    if not os.path.exists(args.sdk_path):
        print("SDK 文档不存在: {}".format(args.sdk_path))
        return 2

    lines = load_lines(args.sdk_path)
    matches = search(lines, args.keywords, args.context)

    if not matches:
        print("未命中关键词: {}".format(", ".join(args.keywords)))
        return 1

    for lineno, snippet in matches[: args.max_results]:
        print("===== line {} =====".format(lineno))
        print(snippet if args.raw else strip_html(snippet))
        print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
