#!/usr/bin/env python3
"""Plan and publish a Markdown document and its local attachments to Wiki.js."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable


SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = SKILL_DIR / "config.json"
PLAN_VERSION = 2
MAX_MCP_MESSAGE = 64 * 1024 * 1024
SUPPORTED_IMAGE_SUFFIXES = {
    ".avif",
    ".bmp",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
}


class PublishError(RuntimeError):
    """A user-actionable planning or publishing failure."""


@dataclass(frozen=True)
class RuntimeConfig:
    mcp_server_name: str
    mcp_config_path: Path
    source_path: Path
    fingerprint: str


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    transport: str
    command: list[str] | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None
    url: str | None = None
    bearer_token_env_var: str | None = None
    http_headers: dict[str, str] | None = None
    env_http_headers: dict[str, str] | None = None

    def public_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name, "transport": self.transport}
        if self.command:
            result["command"] = self.command[0]
            result["arg_count"] = len(self.args or [])
        if self.cwd:
            result["cwd"] = self.cwd
        if self.url:
            parsed = urllib.parse.urlsplit(self.url)
            result["url_origin"] = f"{parsed.scheme}://{parsed.netloc}"
        if self.env:
            result["env_keys"] = sorted(self.env)
        return result


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def path_identity(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PublishError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PublishError(f"Invalid JSON in {path}: {exc}") from exc


def file_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_runtime_config(path: Path) -> RuntimeConfig:
    raw = read_json(path)
    if not isinstance(raw, dict):
        raise PublishError("config.json must contain a JSON object.")

    name = raw.get("mcp_server_name")
    if not isinstance(name, str) or not name.strip():
        raise PublishError("mcp_server_name cannot be empty.")
    config_path = path_identity(path)
    mcp_config_path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
    canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return RuntimeConfig(
        mcp_server_name=name.strip(),
        mcp_config_path=mcp_config_path,
        source_path=config_path,
        fingerprint=file_digest(canonical.encode("utf-8")),
    )


def normalize_wiki_path(value: str, field: str) -> str:
    path = value.strip()
    if path.startswith("/") or path.endswith("/"):
        raise PublishError(f"{field} must not have leading or trailing slashes.")
    if any(part in {"", ".", ".."} for part in path.split("/")):
        raise PublishError(f"{field} contains an empty, '.' or '..' segment.")
    if any(ord(character) < 32 for character in path):
        raise PublishError(f"{field} contains a control character.")
    if len(path) > 2048:
        raise PublishError(f"{field} exceeds Wiki.js's 2048-character path limit.")
    return path


def normalize_title(value: str) -> str:
    title = re.sub(r"\s+", " ", value).strip()
    if not title:
        raise PublishError("The page title cannot be empty.")
    if len(title) > 255:
        raise PublishError("The Wiki.js page title exceeds 255 characters.")
    return title


ADJACENT_BOLD_RE = re.compile(r"(?<![\\*])\*\*([^*\r\n]+)\*\*\*\*([^*\r\n]+)\*\*(?=\*\*|[^*]|$)")
INLINE_MARKER_RE = re.compile(r"(?<!\\)(`+)|<!--|<[^>\r\n]*>")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
BARE_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)


def normalize_bold_text(text: str) -> str:
    while True:
        masked = list(text)
        protected = [(m.start("target"), m.end("target")) for m in MD_LINK_RE.finditer(text)]
        protected.extend((m.start(), m.end()) for m in BARE_URL_RE.finditer(text))
        for start, end in protected:
            for index in range(start, end):
                if masked[index] == "*":
                    masked[index] = "\0"
        match = next(
            (m for m in ADJACENT_BOLD_RE.finditer("".join(masked))
             if "\\" not in text[m.start():m.end()]),
            None,
        )
        if match is None:
            return text
        boundary = match.end(1)
        text = text[:boundary] + text[boundary + 4:]


def normalize_adjacent_bold(markdown: str) -> str:
    """Merge adjacent strong spans without changing code or HTML tags."""
    lines: list[str] = []
    fence: str | None = None
    inline: str | None = None
    html_raw: str | None = None
    for line in markdown.splitlines(keepends=True):
        opening = FENCE_RE.match(line) if inline is None and html_raw is None else None
        if fence:
            if re.match(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*$", line):
                fence = None
            lines.append(line)
            continue
        if opening:
            fence = opening.group(1)
            lines.append(line)
            continue
        if inline is None and html_raw is None and (line.startswith("    ") or line.startswith("\t")):
            lines.append(line)
            continue
        position = 0
        parts: list[str] = []
        while position < len(line):
            if html_raw is not None:
                closing = re.search(html_raw, line[position:], re.IGNORECASE)
                if closing is None:
                    parts.append(line[position:])
                    position = len(line)
                    continue
                end = position + closing.end()
                parts.append(line[position:end])
                position = end
                html_raw = None
                continue
            if inline is not None:
                closing = re.search(r"(?<!`)" + re.escape(inline) + r"(?!`)", line[position:])
                if closing is None:
                    parts.append(line[position:])
                    position = len(line)
                    continue
                end = position + closing.end()
                parts.append(line[position:end])
                position = end
                inline = None
                continue
            marker = INLINE_MARKER_RE.search(line, position)
            end = marker.start() if marker else len(line)
            parts.append(normalize_bold_text(line[position:end]))
            if marker is None:
                break
            parts.append(marker.group(0))
            position = marker.end()
            if marker.group(1):
                inline = marker.group(1)
            elif marker.group(0) == "<!--":
                html_raw = "-->"
            else:
                raw_tag = re.match(r"<\s*(code|pre|script|style|textarea)\b", marker.group(0), re.IGNORECASE)
                if raw_tag and not marker.group(0).rstrip().endswith("/>"):
                    html_raw = r"</\s*" + re.escape(raw_tag.group(1)) + r"\s*>"
        lines.append("".join(parts))
    return "".join(lines)


def strip_frontmatter(markdown: str) -> tuple[str, dict[str, str]]:
    lines = markdown.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return markdown, {}
    for index in range(1, min(len(lines), 100)):
        if lines[index].strip() == "---":
            metadata: dict[str, str] = {}
            for line in lines[1:index]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip().lower()] = value.strip().strip("'\"")
            return "".join(lines[index + 1 :]), metadata
    return markdown, {}


MD_LINK_RE = re.compile(
    r"(?P<prefix>!?\[[^\]\n]*\]\()"
    r"(?P<target><[^>\n]+>|[^\s)\n]+)"
    r"(?P<suffix>(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\))"
)
HTML_ATTR_RE = re.compile(
    r"(?P<prefix>\b(?:src|href)\s*=\s*)(?P<quote>[\"'])(?P<target>.*?)(?P=quote)",
    re.IGNORECASE,
)


def is_external_target(target: str) -> bool:
    lowered = target.lower()
    return (
        lowered.startswith(("#", "/", "//", "data:", "http:", "https:", "mailto:", "tel:", "javascript:"))
        or bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target))
    )


def local_target_path(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split("#", 1)[0].split("?", 1)[0]
    return urllib.parse.unquote(target)


def collect_attachment_refs(markdown: str, markdown_path: Path) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}

    def add(raw_target: str, syntax: str, width: int) -> None:
        if not raw_target or is_external_target(raw_target):
            return
        decoded = local_target_path(raw_target)
        if not decoded or decoded.startswith("/"):
            return
        resolved = path_identity(markdown_path.parent / decoded)
        if not resolved.is_file():
            raise PublishError(
                f"Markdown references a missing local file: {decoded!r} "
                f"(resolved to {resolved})"
            )
        key = os.path.normcase(str(resolved))
        if key in seen:
            seen[key]["raw_targets"].append(raw_target)
            return
        ref = {
                "raw_targets": [raw_target],
                "local_path": str(resolved),
                "syntax": syntax,
                "width": width,
            }
        seen[key] = ref
        refs.append(ref)

    matches = [(m, "markdown") for m in MD_LINK_RE.finditer(markdown)]
    matches.extend((m, "html") for m in HTML_ATTR_RE.finditer(markdown))
    for match, syntax in sorted(matches, key=lambda item: item[0].start()):
        add(match.group("target"), syntax, match.start("target"))
    return refs


def replace_targets(markdown: str, replacements: dict[str, str]) -> str:
    def md_replace(match: re.Match[str]) -> str:
        target = match.group("target")
        replacement = replacements.get(target)
        if replacement is None:
            return match.group(0)
        if target.startswith("<") and target.endswith(">"):
            replacement = f"<{replacement}>"
        return f"{match.group('prefix')}{replacement}{match.group('suffix')}"

    def html_replace(match: re.Match[str]) -> str:
        replacement = replacements.get(match.group("target"))
        if replacement is None:
            return match.group(0)
        return f"{match.group('prefix')}{match.group('quote')}{replacement}{match.group('quote')}"

    return HTML_ATTR_RE.sub(html_replace, MD_LINK_RE.sub(md_replace, markdown))


def load_mcp_config(config: RuntimeConfig) -> McpServerConfig:
    try:
        with config.mcp_config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise PublishError(f"Codex MCP configuration not found: {config.mcp_config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise PublishError(f"Invalid TOML in {config.mcp_config_path}: {exc}") from exc

    servers = data.get("mcp_servers")
    if not isinstance(servers, dict):
        raise PublishError(f"No [mcp_servers] table in {config.mcp_config_path}")
    raw = servers.get(config.mcp_server_name)
    if not isinstance(raw, dict):
        names = ", ".join(sorted(str(name) for name in servers)) or "(none)"
        raise PublishError(
            f'MCP server "{config.mcp_server_name}" is not configured. '
            f"Available names: {names}"
        )
    if raw.get("enabled") is False:
        raise PublishError(f'MCP server "{config.mcp_server_name}" is disabled.')

    url = raw.get("url")
    command = raw.get("command")
    if isinstance(url, str) and url.strip():
        headers = raw.get("http_headers", {})
        if not isinstance(headers, dict):
            raise PublishError(f"http_headers for {config.mcp_server_name} must be a table.")
        env_headers = raw.get("env_http_headers", {})
        if not isinstance(env_headers, dict):
            raise PublishError(f"env_http_headers for {config.mcp_server_name} must be a table.")
        return McpServerConfig(
            name=config.mcp_server_name,
            transport="streamable-http",
            url=url,
            bearer_token_env_var=raw.get("bearer_token_env_var"),
            http_headers={str(k): str(v) for k, v in headers.items()},
            env_http_headers={str(k): str(v) for k, v in env_headers.items()},
        )

    if not isinstance(command, str) or not command.strip():
        raise PublishError(
            f'MCP server "{config.mcp_server_name}" must define either url or command.'
        )
    args = raw.get("args", [])
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise PublishError(f"args for {config.mcp_server_name} must be an array of strings.")
    env = raw.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise PublishError(f"env for {config.mcp_server_name} must map strings to strings.")
    return McpServerConfig(
        name=config.mcp_server_name,
        transport="stdio",
        command=[command],
        args=list(args),
        env=dict(env),
        cwd=raw.get("cwd"),
    )


def select_scheme(server: McpServerConfig, scheme: str | None) -> McpServerConfig:
    if scheme is None:
        return server
    if scheme not in {"http", "https"}:
        raise PublishError("Scheme must be http or https.")
    if server.transport == "stdio":
        env = dict(server.env or {})
        value = env.get("WIKIJS_URL", os.environ.get("WIKIJS_URL", ""))
    else:
        value = server.url or ""
    try:
        parsed = urllib.parse.urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.fragment or parsed.port is not None and not 1 <= parsed.port <= 65535):
            raise ValueError
    except ValueError as exc:
        raise PublishError("Cannot change scheme: the configured URL is missing or invalid.") from exc
    selected = parsed._replace(scheme=scheme).geturl()
    if server.transport == "stdio":
        env["WIKIJS_URL"] = selected
        return replace(server, env=env)
    return replace(server, url=selected)


def build_plan(
    markdown_path: Path, config_path: Path, document_path: str,
    document_name: str | None = None, title: str | None = None, locale: str | None = None,
) -> dict[str, Any]:
    config = load_runtime_config(config_path)
    markdown_path = path_identity(markdown_path)
    if not markdown_path.is_file():
        raise PublishError(f"Markdown file not found: {markdown_path}")
    markdown = markdown_path.read_text(encoding="utf-8")
    body, frontmatter = strip_frontmatter(markdown)
    body = normalize_adjacent_bold(body)
    document_path = normalize_wiki_path(document_path, "document_path")
    name = document_name or markdown_path.stem
    if not re.fullmatch(r"[A-Za-z0-9]+(?:[-_ ][A-Za-z0-9]+)*", name):
        raise PublishError("Provide an English document name using --document-name.")
    name = re.sub(r"[-_ ]+", "-", name.lower())
    attachment_path = f"assets/{name}"
    if locale is not None:
        locale = locale.lower().strip()
        if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2,4})?", locale):
            raise PublishError("locale must look like en, de, or zh-cn.")
    page_title = normalize_title(
        title or frontmatter.get("title") or markdown_path.stem
    )
    mcp = load_mcp_config(config)
    refs = collect_attachment_refs(body, markdown_path)
    counters = {"image": 0, "pdf": 0}
    assets: list[dict[str, Any]] = []
    replacements: dict[str, str] = {}
    for ref in refs:
        local_path = Path(ref["local_path"])
        data = local_path.read_bytes()
        if not data:
            raise PublishError(f"Attachment is empty: {local_path}")
        digest = file_digest(data)
        suffix = local_path.suffix.lower()
        category = "image" if suffix in SUPPORTED_IMAGE_SUFFIXES else "pdf" if suffix == ".pdf" else None
        if category is None:
            raise PublishError(f"Unsupported attachment type: {local_path}. Only images and PDFs are supported.")
        counters[category] += 1
        if counters[category] > 9999:
            raise PublishError(f"More than 9999 {category} attachments.")
        remote_name = f"{category}_{counters[category]:04d}{suffix}"
        folder_url = "/".join(urllib.parse.quote(part) for part in attachment_path.split("/"))
        relative_url = f"{folder_url}/{urllib.parse.quote(remote_name)}"
        url = f"/{relative_url}"
        for target in ref["raw_targets"]:
            replacements[target] = url
        assets.append(
            {
                "source_path": str(local_path),
                "filename": remote_name,
                "suffix": suffix,
                "sha256": digest,
                "size": len(data),
                "url": url,
                "asset_kind": "IMAGE" if suffix in SUPPORTED_IMAGE_SUFFIXES else "BINARY",
            }
        )
    rewritten = replace_targets(body, replacements)
    return {
        "version": PLAN_VERSION,
        "kind": "markdown-to-wikijs-plan",
        "created_at": int(time.time()),
        "config": {
            "path": str(config.source_path),
            "fingerprint": config.fingerprint,
            "mcp_server_name": config.mcp_server_name,
            "mcp_config_path": str(config.mcp_config_path),
        },
        "source": {
            "markdown_path": str(markdown_path),
            "markdown_sha256": file_digest(markdown.encode("utf-8")),
        },
        "options": {"document_path": document_path, "document_name": name, "title": title, "locale": locale},
        "mcp": mcp.public_dict(),
        "page": {
            "path": document_path,
            "title": page_title,
            "locale": locale,
            "editor": "markdown",
        },
        "asset_folder_path": attachment_path,
        "assets": assets,
        "markdown": rewritten,
    }


class McpClient:
    """Small MCP JSON-RPC client for the transports Codex can configure."""

    def __init__(self, server: McpServerConfig):
        self.server = server
        self.process: subprocess.Popen[str] | None = None
        self.session_id: str | None = None
        self.protocol_version: str | None = None
        self.next_id = 1
        self.write_lock = threading.Lock()
        self.responses: queue.Queue[dict[str, Any]] = queue.Queue()

    def __enter__(self) -> "McpClient":
        if self.server.transport == "stdio":
            env = os.environ.copy()
            env.update(self.server.env or {})
            command = prepare_stdio_command([*(self.server.command or []), *(self.server.args or [])])
            try:
                self.process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.server.cwd,
                    env=env,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
            except OSError as exc:
                raise PublishError(f"Could not launch MCP server {self.server.name}: {exc}") from exc
            threading.Thread(target=self._read_stdout, daemon=True).start()
            threading.Thread(target=self._read_stderr, daemon=True).start()
        try:
            self._initialize()
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def _read_stdout(self) -> None:
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if "id" in message and "method" not in message:
                self.responses.put(message)
                continue
            if isinstance(message.get("id"), int) and "method" in message:
                self._reply_to_server(message)

    def _read_stderr(self) -> None:
        assert self.process and self.process.stderr
        for line in self.process.stderr:
            line = line.strip()
            if line:
                eprint(f"[{self.server.name}] {line}")

    def _reply_to_server(self, message: dict[str, Any]) -> None:
        request_id = message.get("id")
        method = message.get("method")
        if method == "elicitation/create":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": "The headless publisher cannot ask a person."},
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"protocolVersion": self.protocol_version or "2025-06-18", "capabilities": {}, "serverInfo": {"name": "markdown-to-wikijs", "version": "1"}},
            }
        self._write_json(response)

    def _write_json(self, message: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise PublishError("MCP process is not running.")
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with self.write_lock:
            self.process.stdin.write(payload + "\n")
            self.process.stdin.flush()

    def _http_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        for key, value in (self.server.http_headers or {}).items():
            headers[key] = value
        for key, variable in (self.server.env_http_headers or {}).items():
            value = os.environ.get(variable, "")
            if value:
                headers[key] = value
        if self.server.bearer_token_env_var:
            token = os.environ.get(self.server.bearer_token_env_var, "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        if self.protocol_version:
            headers["MCP-Protocol-Version"] = self.protocol_version
        return headers

    def _http_request(self, payload: dict[str, Any], request_id: int | None = None) -> dict[str, Any]:
        import urllib.error
        import urllib.request

        assert self.server.url
        request = urllib.request.Request(
            self.server.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self._http_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self.session_id = session_id
                body = response.read(MAX_MCP_MESSAGE).decode("utf-8", errors="replace")
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            body = exc.read(8192).decode("utf-8", errors="replace")
            raise PublishError(f"MCP HTTP {exc.code} for {self.server.name}: {body}") from exc
        except urllib.error.URLError as exc:
            raise PublishError(f"Could not reach MCP {self.server.name}: {exc.reason}") from exc
        if "text/event-stream" in content_type:
            messages = parse_sse_messages(body)
            for message in messages:
                if request_id is not None and message.get("id") == request_id:
                    return message
            raise PublishError("MCP SSE response ended without the requested message.")
        try:
            message = json.loads(body)
        except json.JSONDecodeError as exc:
            raise PublishError(f"MCP returned invalid JSON: {body[:1000]}") from exc
        if not isinstance(message, dict):
            raise PublishError("MCP returned a non-object JSON response.")
        return message

    def _initialize(self) -> None:
        version = "2025-06-18"
        response = self.request(
            "initialize",
            {
                "protocolVersion": version,
                "capabilities": {"elicitation": {}},
                "clientInfo": {"name": "markdown-to-wikijs", "version": "1"},
            },
            initialize=True,
        )
        result = response.get("result", {})
        if not isinstance(result, dict):
            raise PublishError("MCP initialize returned no result.")
        self.protocol_version = str(result.get("protocolVersion") or version)
        self.notify("notifications/initialized", {})

    def notify(self, method: str, params: dict[str, Any]) -> None:
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if self.server.transport == "stdio":
            self._write_json(message)
        else:
            self._http_notification(message)

    def _http_notification(self, payload: dict[str, Any]) -> None:
        import urllib.error
        import urllib.request
        assert self.server.url
        request = urllib.request.Request(
            self.server.url, data=json.dumps(payload).encode("utf-8"),
            headers=self._http_headers(), method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90):
                pass
        except urllib.error.URLError as exc:
            raise PublishError(f"Could not send MCP notification to {self.server.name}: {exc.reason}") from exc

    def request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        initialize: bool = False,
    ) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        if self.server.transport == "stdio":
            self._write_json(payload)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                try:
                    response = self.responses.get(timeout=0.25)
                except queue.Empty:
                    if self.process and self.process.poll() is not None:
                        raise PublishError(
                            f"MCP server {self.server.name} exited with code {self.process.returncode}."
                        )
                    continue
                if response.get("id") == request_id:
                    return response
            raise PublishError(f"Timed out waiting for MCP response to {method}.")

        response = self._http_request(payload, request_id)
        if initialize:
            return response
        return response

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        response = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        if "error" in response:
            raise PublishError(f"MCP tool {name} failed: {response['error']}")
        result = response.get("result")
        if not isinstance(result, dict):
            raise PublishError(f"MCP tool {name} returned no result.")
        if result.get("isError"):
            texts = [
                item.get("text", "")
                for item in result.get("content", [])
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            raise PublishError(f"Wiki.js tool {name} failed: {' '.join(texts).strip()}")
        if "structuredContent" in result:
            return result["structuredContent"]
        texts = [
            item.get("text", "")
            for item in result.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except json.JSONDecodeError:
                return texts[0]
        return texts

    def list_tools(self) -> list[dict[str, Any]]:
        response = self.request("tools/list", {})
        if "error" in response:
            raise PublishError(f"MCP tools/list failed: {response['error']}")
        result = response.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
            raise PublishError("MCP tools/list returned no tools array.")
        return [tool for tool in result["tools"] if isinstance(tool, dict)]


def parse_sse_messages(body: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for event in re.split(r"\r?\n\r?\n", body):
        data_lines = [
            line[5:].lstrip()
            for line in event.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        try:
            message = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict):
            messages.append(message)
    return messages


def prepare_stdio_command(command: list[str]) -> list[str]:
    """Resolve a Windows executable before using subprocess without a shell."""
    if os.name != "nt":
        return command
    resolved = shutil.which(command[0])
    if not resolved:
        return command
    path = Path(resolved)
    if path.suffix.lower() == ".cmd" and path.name.lower() in {"npx.cmd", "npm.cmd"}:
        node = path.with_name("node.exe")
        cli = path.parent / "node_modules" / "npm" / "bin" / f"{path.stem}-cli.js"
        if node.is_file() and cli.is_file():
            return [str(node), str(cli), *command[1:]]
    return [str(path), *command[1:]]


def item_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def list_from_result(result: Any, keys: Iterable[str] = ("items", "pages", "assets", "folders")) -> list[Any]:
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        if result.get("truncated"):
            raise PublishError("Wiki.js returned a truncated asset or folder list; cannot safely check names.")
        for key in keys:
            value = result.get(key)
            if isinstance(value, list):
                return value
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return list_from_result(structured, keys)
    return []


def find_page(client: McpClient, page: dict[str, Any]) -> dict[str, Any] | None:
    try:
        arguments = {"path": page["path"], "mode": "metadata"}
        if page["locale"] is not None:
            arguments["locale"] = page["locale"]
        result = client.call_tool(
            "get_page",
            arguments,
        )
    except PublishError as exc:
        message = str(exc).lower()
        if "not found" in message or "does not exist" in message or "no page with that id or path" in message:
            return None
        raise
    if isinstance(result, dict):
        nested = result.get("page")
        if isinstance(nested, dict):
            return nested
        if result.get("id") is not None:
            return result
    return None


def slugify_asset_segment(segment: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", segment.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if slug:
        return slug
    return f"assets-{hashlib.sha256(segment.encode('utf-8')).hexdigest()[:8]}"


def ensure_asset_folder(client: McpClient, path: str) -> tuple[int, list[str]]:
    current = 0
    actual_segments: list[str] = []
    for segment in path.split("/"):
        expected_slug = slugify_asset_segment(segment)
        result = client.call_tool("list_asset_folders", {"parent_folder_id": current})
        folders = list_from_result(result, ("folders", "items"))
        matched = next(
            (
                folder
                for folder in folders
                if str(item_value(folder, "slug", "")) == expected_slug
            ),
            None,
        )
        if matched is not None:
            actual_segments.append(expected_slug)
            current = int(item_value(matched, "id"))
            continue
        client.call_tool(
            "create_asset_folder",
            {"parent_folder_id": current, "slug": expected_slug, "name": segment},
        )
        result = client.call_tool("list_asset_folders", {"parent_folder_id": current})
        folders = list_from_result(result, ("folders", "items"))
        matched = next(
            (
                folder
                for folder in folders
                if str(item_value(folder, "slug", "")) == expected_slug
            ),
            None,
        )
        if matched is None:
            raise PublishError(f"Created asset folder {expected_slug!r} but could not find it again.")
        actual_segments.append(expected_slug)
        current = int(item_value(matched, "id"))
    return current, actual_segments


def list_assets(client: McpClient, folder_id: int, kind: str) -> list[Any]:
    result = client.call_tool("list_assets", {"folder_id": folder_id, "kind": kind})
    return list_from_result(result, ("assets", "items"))


def asset_url(asset: dict[str, Any], folder_segments: list[str], url_prefix: str) -> str:
    filename = str(item_value(asset, "filename", ""))
    if not filename:
        raise PublishError("Wiki.js returned an uploaded asset without a filename.")
    segments = [*folder_segments, filename]
    relative = "/".join(urllib.parse.quote(part) for part in segments)
    return f"{url_prefix}/{relative}"


class RenderedResources(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: set[str] = set()
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "img" and attributes.get("src"):
            self.images.add(str(attributes["src"]))
        elif tag == "a" and attributes.get("href"):
            self.links.add(str(attributes["href"]))


class NoAssetRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


def verify_rendered_assets(
    client: McpClient,
    mcp: McpServerConfig,
    page_id: int,
    markdown: str,
    assets: list[dict[str, Any]],
    urls: dict[str, str],
) -> dict[str, Any]:
    if not assets:
        return {"status": "not_applicable", "rendered": 0, "downloaded": 0}
    rendered = client.call_tool("get_page", {"page_id": page_id, "mode": "rendered"})
    html = rendered.get("render") if isinstance(rendered, dict) else None
    if not isinstance(html, str):
        raise PublishError("Page was published, but rendered HTML is unavailable for asset verification.")
    parser = RenderedResources()
    parser.feed(html)

    expected: dict[str, set[str]] = {urls[asset["url"]]: set() for asset in assets}
    for match in MD_LINK_RE.finditer(markdown):
        target = match.group("target").strip("<>")
        if target in expected:
            expected[target].add("image" if match.group("prefix").startswith("!") else "link")
    for match in HTML_ATTR_RE.finditer(markdown):
        target = match.group("target")
        if target in expected:
            expected[target].add("image" if match.group("prefix").lower().lstrip().startswith("src") else "link")
    for url, kinds in expected.items():
        if not kinds or ("image" in kinds and url not in parser.images) or ("link" in kinds and url not in parser.links):
            raise PublishError(f"Page was published, but its rendered HTML is missing the expected resource: {url}")

    if mcp.transport != "stdio":
        return {"status": "incomplete", "rendered": len(assets), "downloaded": 0,
                "reason": "The MCP transport does not expose the Wiki.js asset endpoint and credentials."}
    env = {**os.environ, **(mcp.env or {})}
    wiki_url = env.get("WIKIJS_URL", "").strip()
    token = (env.get("WIKIJS_TOKEN") or env.get("WIKIJS_API_KEY") or "").strip()
    endpoint = urllib.parse.urlsplit(wiki_url)
    if (not token or endpoint.scheme not in {"http", "https"} or not endpoint.hostname
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment):
        return {"status": "incomplete", "rendered": len(assets), "downloaded": 0,
                "reason": "The Wiki.js URL or token is unavailable for authenticated asset checks."}

    origin = f"{endpoint.scheme}://{endpoint.netloc}"
    opener = urllib.request.build_opener(NoAssetRedirect())
    for asset in assets:
        url = urls[asset["url"]]
        parts = urllib.parse.urlsplit(url)
        if not url.startswith("/") or url.startswith("//") or parts.scheme or parts.netloc or parts.query or parts.fragment:
            raise PublishError("Page was published, but an asset URL is not a safe root-relative path.")
        request = urllib.request.Request(origin + url, headers={"Authorization": f"Bearer {token}"})
        try:
            with opener.open(request, timeout=30) as response:
                digest = hashlib.sha256()
                remaining = int(asset["size"]) + 1
                while remaining:
                    chunk = response.read(min(65536, remaining))
                    if not chunk:
                        break
                    digest.update(chunk)
                    remaining -= len(chunk)
        except urllib.error.HTTPError as exc:
            exc.close()
            raise PublishError(f"Page was published, but asset {url} returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise PublishError(f"Page was published, but asset {url} could not be downloaded.") from exc
        if remaining != 1 or digest.hexdigest() != asset["sha256"]:
            raise PublishError(f"Page was published, but asset {url} differs from the source file.")
    return {"status": "passed", "rendered": len(assets), "downloaded": len(assets)}


def apply_plan(plan: dict[str, Any], dry_run: bool, replace: bool,
               scheme: str | None = None) -> dict[str, Any]:
    if plan.get("kind") != "markdown-to-wikijs-plan" or plan.get("version") != PLAN_VERSION:
        raise PublishError("The plan has an unsupported kind or version. Create it again.")
    config_path = Path(str(plan.get("config", {}).get("path", "")))
    source_path = Path(str(plan["source"]["markdown_path"]))
    if not source_path.is_file():
        raise PublishError(f"Source Markdown no longer exists: {source_path}")
    if file_digest(source_path.read_text(encoding="utf-8").encode("utf-8")) != plan["source"]["markdown_sha256"]:
        raise PublishError("Source Markdown changed after planning. Create a new plan.")
    for asset in plan["assets"]:
        local_path = Path(asset["source_path"])
        if not local_path.is_file() or file_digest(local_path.read_bytes()) != asset["sha256"]:
            raise PublishError(f"Attachment disappeared or changed after planning: {local_path}")
    current = load_runtime_config(config_path)
    planned = plan.get("config", {})
    if planned.get("fingerprint") != current.fingerprint:
        eprint("Configuration changed since planning; rebuilding the plan with current settings.")
        plan = build_plan(source_path, config_path, **plan["options"])
        planned = plan["config"]

    mcp = select_scheme(load_mcp_config(current), scheme)

    page = plan["page"]
    planned_markdown = str(plan["markdown"])
    markdown = planned_markdown
    result: dict[str, Any] = {
        "mcp_server": current.mcp_server_name,
        "page": {"path": page["path"], "locale": page["locale"], "title": page["title"]},
        "dry_run": dry_run,
        "uploaded": [],
        "reused": [],
        "created": False,
        "updated": False,
    }
    with McpClient(mcp) as client:
        existing = find_page(client, page)
        if existing is not None:
            result["page"]["id"] = item_value(existing, "id")
        if dry_run:
            folder_result = client.call_tool("list_asset_folders", {"parent_folder_id": 0})
            result["root_asset_folders"] = len(list_from_result(folder_result, ("folders", "items")))
            return result

        if existing is not None and not replace:
            raise PublishError("Page already exists. Confirm replacement and use --replace.")

        for asset in plan["assets"]:
            local_path = Path(asset["source_path"])
            if not local_path.is_file() or file_digest(local_path.read_bytes()) != asset["sha256"]:
                raise PublishError(f"Attachment disappeared or changed after planning: {local_path}")

        folder_id, folder_segments = (0, [])
        if plan["assets"]:
            folder_id, folder_segments = ensure_asset_folder(client, plan["asset_folder_path"])
        result["asset_folder_id"] = folder_id
        existing_assets = list_assets(client, folder_id, "ALL") if plan["assets"] else []
        existing_names = {str(item_value(item, "filename", "")).lower() for item in existing_assets}
        conflicts = [asset["filename"] for asset in plan["assets"] if asset["filename"].lower() in existing_names]
        if conflicts:
            raise PublishError("Remote assets already exist; cannot verify their contents or overwrite them: " + ", ".join(conflicts))
        replacements: dict[str, str] = {}
        for asset in plan["assets"]:
            local_path = Path(asset["source_path"])
            data = local_path.read_bytes()
            if file_digest(data) != asset["sha256"]:
                raise PublishError(f"Attachment changed after planning: {local_path}")
            kind = asset["asset_kind"]
            client.call_tool(
                "upload_asset",
                {
                    "filename": asset["filename"],
                    "content_base64": base64.b64encode(data).decode("ascii"),
                    "folder_id": folder_id,
                },
            )
            result["uploaded"].append(asset["filename"])
            matched = next(
                (remote for remote in list_assets(client, folder_id, kind)
                 if str(item_value(remote, "filename", "")) == asset["filename"]),
                None,
            )
            if matched is None:
                raise PublishError(
                    f"Uploaded {asset['filename']} but Wiki.js did not list it in folder {folder_id}."
                )
            replacements[asset["url"]] = asset_url(
                matched, folder_segments, ""
            )

        markdown = replace_targets(markdown, replacements)
        if existing is None:
            arguments = {
                "path": page["path"],
                "title": page["title"],
                "content": markdown,
                "editor": "markdown",
                "is_published": True,
            }
            if page["locale"] is not None:
                arguments["locale"] = page["locale"]
            client.call_tool(
                "create_page",
                arguments,
            )
            result["created"] = True
        else:
            client.call_tool(
                "update_page",
                {
                    "page_id": item_value(existing, "id"),
                    "content": markdown,
                    "editor": "markdown",
                    "force": False,
                },
            )
            result["updated"] = True

        verified = find_page(client, page)
        if verified is None:
            raise PublishError("Page write completed but the page could not be read back.")
        result["page"]["locale"] = item_value(verified, "locale", page["locale"])
        content = read_page_content(client, item_value(verified, "id"), page["locale"])
        if content != markdown:
            raise PublishError("Page was written, but its source does not match the published Markdown.")
        missing_urls = [
            url for url in replacements.values() if url not in content
        ]
        if missing_urls:
            raise PublishError(
                "Page was written, but verification did not find these asset URLs in "
                f"its source: {', '.join(missing_urls)}"
            )
        result["verified_assets"] = len(plan["assets"])
        result["resource_verification"] = verify_rendered_assets(
            client, mcp, item_value(verified, "id"), content, plan["assets"], replacements
        )
        return result


def read_page_content(client: McpClient, page_id: int, locale: str | None) -> str:
    chunks: list[str] = []
    offset = 0
    while True:
        arguments = {
            "page_id": page_id, "mode": "content",
            "offset": offset, "max_chars": 200000,
        }
        if locale is not None:
            arguments["locale"] = locale
        result = client.call_tool("get_page", arguments)
        content = result.get("content") if isinstance(result, dict) else result
        if isinstance(content, str):
            return "".join(chunks) + content
        if not isinstance(content, dict) or not isinstance(content.get("text"), str):
            raise PublishError("Could not read published page source for verification.")
        chunks.append(content["text"])
        if not content.get("truncated"):
            return "".join(chunks)
        returned = content.get("returnedChars")
        if not isinstance(returned, int) or returned <= 0:
            raise PublishError("Wiki.js returned an invalid page content window.")
        offset += returned


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_plan(args: argparse.Namespace) -> int:
    plan = build_plan(Path(args.markdown), Path(args.config), args.document_path,
                      args.document_name, args.title, args.locale)
    if args.output:
        output = Path(args.output)
        write_json(output, plan)
        eprint(f"Plan written to {output}")
    summary = {
        "mcp": plan["mcp"],
        "page": plan["page"],
        "asset_folder_path": plan["asset_folder_path"],
        "assets": [
            {
                "source": Path(asset["source_path"]).name,
                "filename": asset["filename"],
                "size": asset["size"],
                "kind": asset["asset_kind"],
            }
            for asset in plan["assets"]
        ],
        "markdown_preview": plan["markdown"][:500],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    plan = read_json(Path(args.plan))
    if not isinstance(plan, dict):
        raise PublishError("Plan must be a JSON object.")
    result = apply_plan(plan, args.dry_run, args.replace, args.scheme)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    verification = result.get("resource_verification", {})
    return 3 if verification.get("status") == "incomplete" else 0


def cmd_verify(args: argparse.Namespace) -> int:
    plan = build_plan(Path(args.markdown), Path(args.config), args.document_path,
                      args.document_name, args.title, args.locale)
    config = load_runtime_config(Path(args.config))
    mcp = select_scheme(load_mcp_config(config), args.scheme)
    with McpClient(mcp) as client:
        page = find_page(client, plan["page"])
        if page is None:
            raise PublishError("The Wiki.js page could not be found for verification.")
        content = read_page_content(client, item_value(page, "id"), plan["page"]["locale"])
        urls = {asset["url"]: asset["url"] for asset in plan["assets"]}
        result = verify_rendered_assets(client, mcp, item_value(page, "id"),
                                        content, plan["assets"], urls)
    print(json.dumps({"page": plan["page"]["path"], "resource_verification": result},
                     ensure_ascii=False, indent=2))
    return 3 if result["status"] == "incomplete" else 0


def cmd_check(args: argparse.Namespace) -> int:
    config = load_runtime_config(Path(args.config))
    mcp = select_scheme(load_mcp_config(config), args.scheme)
    with McpClient(mcp) as client:
        tools = client.list_tools()
    names = {str(tool.get("name", "")) for tool in tools}
    required = {
        "get_page",
        "create_page",
        "update_page",
        "list_asset_folders",
        "create_asset_folder",
        "upload_asset",
        "list_assets",
    }
    missing = sorted(required - names)
    result = {
        "mcp_server": config.mcp_server_name,
        "transport": mcp.transport,
        "tool_count": len(tools),
        "required_tools_present": not missing,
        "missing_tools": missing,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not missing else 3


def cmd_normalize(args: argparse.Namespace) -> int:
    path = Path(args.markdown)
    if not path.is_file():
        raise PublishError(f"Markdown file not found: {path}")
    with path.open(encoding="utf-8", newline="") as stream:
        original = stream.read()
    body, _ = strip_frontmatter(original)
    header = original[:len(original) - len(body)]
    normalized = header + normalize_adjacent_bold(body)
    if normalized != original:
        with path.open("w", encoding="utf-8", newline="") as stream:
            stream.write(normalized)
    print(json.dumps({"markdown": str(path), "changed": normalized != original}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or publish a Markdown document to Wiki.js via a configured MCP."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Build a local publish plan.")
    plan_parser.add_argument("--markdown", required=True, help="Markdown file to publish.")
    plan_parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Skill config.json.")
    plan_parser.add_argument("--document-path", required=True, help="Complete Wiki.js page path.")
    plan_parser.add_argument("--document-name", help="English document name used for the asset folder.")
    plan_parser.add_argument("--locale", help="Wiki.js locale (default: MCP server's locale).")
    plan_parser.add_argument("--title", help="Override the Wiki.js page title.")
    plan_parser.add_argument("--output", help="Write the complete plan to this JSON file.")
    plan_parser.set_defaults(func=cmd_plan)

    normalize_parser = subparsers.add_parser("normalize", help="Fix adjacent bold spans in local Markdown.")
    normalize_parser.add_argument("--markdown", required=True, help="Markdown file to update in place.")
    normalize_parser.set_defaults(func=cmd_normalize)

    verify_parser = subparsers.add_parser("verify", help="Check a published page and its resources without writing.")
    verify_parser.add_argument("--markdown", required=True, help="Local Markdown file.")
    verify_parser.add_argument("--document-path", required=True, help="Complete Wiki.js page path.")
    verify_parser.add_argument("--document-name", help="English document name used for the asset folder.")
    verify_parser.add_argument("--locale", help="Wiki.js locale (default: MCP server's locale).")
    verify_parser.add_argument("--title", help="Override the Wiki.js page title.")
    verify_parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Skill config.json.")
    verify_parser.add_argument("--scheme", choices=("http", "https"),
                               help="Explicitly use this URL scheme for this invocation.")
    verify_parser.set_defaults(func=cmd_verify)

    apply_parser = subparsers.add_parser("apply", help="Publish a previously reviewed plan.")
    apply_parser.add_argument("--plan", required=True, help="JSON plan created by this script.")
    apply_parser.add_argument("--dry-run", action="store_true", help="Connect and read only.")
    apply_parser.add_argument("--scheme", choices=("http", "https"),
                              help="Explicitly use this URL scheme for this invocation.")
    apply_parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing page after explicit user confirmation.",
    )
    apply_parser.set_defaults(func=cmd_apply)

    check_parser = subparsers.add_parser(
        "check", help="Verify the configured MCP and required Wiki.js tools."
    )
    check_parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Skill config.json.")
    check_parser.add_argument("--scheme", choices=("http", "https"),
                              help="Explicitly use this URL scheme for this invocation.")
    check_parser.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except PublishError as exc:
        eprint(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
