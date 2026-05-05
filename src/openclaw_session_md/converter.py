from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator


@dataclass(slots=True)
class ConvertOptions:
    include_tools: bool = False
    redact_metadata: bool = False
    max_text_chars: int = 6000


@dataclass(slots=True)
class SessionMeta:
    session_id: str | None = None
    session_key: str | None = None
    started_at: str | None = None
    cwd: str | None = None
    provider: str | None = None
    model_id: str | None = None
    source: str | None = None
    event_count: int = 0
    message_count: int = 0


def find_session_files(
    input_path: Path,
    *,
    include_trajectory: bool = False,
    include_checkpoints: bool = False,
) -> list[Path]:
    input_path = input_path.expanduser()
    if input_path.is_file():
        return [input_path]
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    if not input_path.is_dir():
        raise ValueError(f"not a file or directory: {input_path}")

    files: list[Path] = []
    for path in sorted(input_path.glob("*.jsonl"), key=lambda p: (p.stat().st_mtime, p.name)):
        name = path.name
        if not include_trajectory and name.endswith(".trajectory.jsonl"):
            continue
        if not include_checkpoints and ".checkpoint." in name:
            continue
        files.append(path)
    return files


def convert_path(
    input_path: Path,
    *,
    output: str | None = None,
    options: ConvertOptions | None = None,
    include_trajectory: bool = False,
    include_checkpoints: bool = False,
    write_index: bool = False,
) -> list[str]:
    options = options or ConvertOptions()
    input_path = input_path.expanduser()

    if input_path.is_file():
        markdown, _meta = convert_file(input_path, options=options)
        if output == "-" or output is None:
            print(markdown)
            return []
        out_path = Path(output).expanduser()
        if out_path.exists() and out_path.is_dir():
            out_path = out_path / f"{input_path.stem}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
        return [str(out_path)]

    files = find_session_files(
        input_path,
        include_trajectory=include_trajectory,
        include_checkpoints=include_checkpoints,
    )
    if output is None or output == "-":
        raise ValueError("directory conversion requires --output DIRECTORY")
    out_dir = Path(output).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    index_rows: list[tuple[Path, SessionMeta]] = []
    for file_path in files:
        markdown, meta = convert_file(file_path, options=options)
        out_path = out_dir / f"{file_path.stem}.md"
        out_path.write_text(markdown, encoding="utf-8")
        written.append(str(out_path))
        index_rows.append((out_path, meta))

    if write_index:
        index_path = out_dir / "index.md"
        index_path.write_text(_render_index(index_rows, out_dir), encoding="utf-8")
        written.append(str(index_path))
    return written


def convert_file(path: Path, *, options: ConvertOptions | None = None) -> tuple[str, SessionMeta]:
    options = options or ConvertOptions()
    records = list(_iter_jsonl(path))
    meta = _collect_meta(records, path)
    lines: list[str] = [_title_for(path, meta), ""]
    lines.extend(_front_matter(path, meta))
    lines.append("")

    if _is_trajectory(records):
        lines.extend(_render_trajectory(records, meta, options))
    else:
        lines.extend(_render_session(records, meta, options))

    return "\n".join(lines).rstrip() + "\n", meta


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.expanduser().open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                yield {
                    "type": "_parse_error",
                    "timestamp": None,
                    "line": line_no,
                    "error": str(exc),
                    "raw": line,
                }
                continue
            if isinstance(obj, dict):
                yield obj
            else:
                yield {"type": "_non_object", "line": line_no, "value": obj}


def _is_trajectory(records: list[dict[str, Any]]) -> bool:
    return any(r.get("traceSchema") == "openclaw-trajectory" for r in records)


def _collect_meta(records: list[dict[str, Any]], path: Path) -> SessionMeta:
    meta = SessionMeta(event_count=len(records))
    for record in records:
        if record.get("type") == "session":
            meta.session_id = meta.session_id or record.get("id")
            meta.started_at = meta.started_at or record.get("timestamp")
            meta.cwd = meta.cwd or record.get("cwd")
        if record.get("traceSchema") == "openclaw-trajectory":
            meta.session_id = meta.session_id or record.get("sessionId")
            meta.session_key = meta.session_key or record.get("sessionKey")
            meta.started_at = meta.started_at or record.get("ts")
            meta.cwd = meta.cwd or record.get("workspaceDir")
            meta.provider = meta.provider or record.get("provider")
            meta.model_id = meta.model_id or record.get("modelId")
            meta.source = meta.source or record.get("source")
        if record.get("type") == "model_change":
            meta.provider = meta.provider or record.get("provider")
            meta.model_id = meta.model_id or record.get("modelId")
        if record.get("type") == "message":
            meta.message_count += 1
    if meta.session_id is None:
        meta.session_id = path.name.split(".")[0]
    return meta


def _title_for(path: Path, meta: SessionMeta) -> str:
    title = meta.session_id or path.stem
    return f"# OpenClaw session: `{_escape_inline(title)}`"


def _front_matter(path: Path, meta: SessionMeta) -> list[str]:
    rows = [
        ("Source file", str(path.expanduser())),
        ("Started", meta.started_at),
        ("Session key", meta.session_key),
        ("Working directory", meta.cwd),
        ("Provider", meta.provider),
        ("Model", meta.model_id),
        ("Events", str(meta.event_count)),
        ("Messages", str(meta.message_count) if meta.message_count else None),
    ]
    out = ["## Metadata"]
    for key, value in rows:
        if value:
            out.append(f"- **{key}:** `{_escape_inline(value)}`")
    return out


def _render_session(records: list[dict[str, Any]], meta: SessionMeta, options: ConvertOptions) -> list[str]:
    out = ["## Transcript", ""]
    for record in records:
        rtype = record.get("type")
        ts = record.get("timestamp") or record.get("ts")
        if rtype == "message":
            msg = record.get("message") or {}
            role = str(msg.get("role", "message")).title()
            text = _message_to_markdown(msg, options)
            if not text.strip() and not options.include_tools:
                continue
            out.extend(_section(role, ts, text))
        elif rtype in {"tool_call", "tool_result"}:
            if options.include_tools:
                out.extend(_section(str(rtype).replace("_", " ").title(), ts, _json_block(record)))
        elif rtype == "model_change":
            provider = record.get("provider", "")
            model = record.get("modelId", "")
            out.append(f"> **Model:** `{_escape_inline(provider)}/{_escape_inline(model)}`")
            out.append("")
        elif rtype == "thinking_level_change":
            out.append(f"> **Thinking level:** `{_escape_inline(str(record.get('thinkingLevel', '')))}`")
            out.append("")
        elif rtype == "_parse_error":
            out.extend(_section("Parse Error", ts, _json_block(record)))
    if len(out) == 2:
        out.append("_No chat messages found._")
    return out


def _render_trajectory(records: list[dict[str, Any]], meta: SessionMeta, options: ConvertOptions) -> list[str]:
    out = ["## Timeline", ""]
    for record in records:
        rtype = record.get("type", "event")
        ts = record.get("ts") or record.get("timestamp")
        data = record.get("data") or {}
        if rtype == "prompt.submitted":
            out.extend(_section("User Prompt", ts, _format_text(data.get("prompt", ""), options)))
        elif rtype == "model.completed":
            assistant_texts = data.get("assistantTexts") or []
            usage = data.get("usage") or {}
            body_parts = []
            if usage:
                body_parts.append(_usage_line(usage))
            if assistant_texts:
                body_parts.append("\n\n".join(_format_text(str(t), options) for t in assistant_texts))
            if options.include_tools and data:
                body_parts.append(_json_block({"data": data}))
            out.extend(_section("Assistant", ts, "\n\n".join(p for p in body_parts if p)))
        elif rtype in {"tool.call", "tool.result", "tool.error"}:
            if options.include_tools:
                title = str(rtype).replace(".", " ").title()
                out.extend(_section(title, ts, _json_block(data or record)))
            else:
                name = data.get("name") or data.get("tool") or record.get("source") or "tool"
                status = "errored" if rtype == "tool.error" else "ran"
                out.append(f"> `{_escape_inline(str(ts or ''))}` tool `{_escape_inline(str(name))}` {status}.")
                out.append("")
        elif rtype in {"session.started", "trace.metadata", "context.compiled"}:
            continue
        elif options.include_tools:
            out.extend(_section(str(rtype), ts, _json_block(data or record)))
    if len(out) == 2:
        out.append("_No timeline events found._")
    return out


def _message_to_markdown(message: dict[str, Any], options: ConvertOptions) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return _format_text(content, options)
    if not isinstance(content, list):
        return _format_text(str(content), options)

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            parts.append(_format_text(str(item), options))
            continue
        ctype = item.get("type")
        if ctype == "text":
            parts.append(_format_text(str(item.get("text", "")), options))
        elif ctype in {"toolCall", "tool_call"}:
            name = item.get("name", "tool")
            if options.include_tools:
                parts.append(f"<details>\n<summary>Tool call: `{_escape_inline(str(name))}`</summary>\n\n{_json_block(item)}\n</details>")
            else:
                parts.append(f"> Tool call: `{_escape_inline(str(name))}`")
        elif ctype in {"toolResult", "tool_result"}:
            if options.include_tools:
                parts.append(f"<details>\n<summary>Tool result</summary>\n\n{_json_block(item)}\n</details>")
        elif ctype in {"image", "image_url"}:
            url = item.get("url") or item.get("image_url", {}).get("url") or item.get("path")
            if url:
                parts.append(f"![image]({_escape_url(str(url))})")
            else:
                parts.append("_[image attachment]_")
        else:
            if options.include_tools:
                parts.append(_json_block(item))
            else:
                parts.append(f"_[{ctype or 'unknown'} content omitted]_")
    return "\n\n".join(p for p in parts if p is not None).strip()


def _format_text(text: str, options: ConvertOptions) -> str:
    if options.redact_metadata:
        text = _redact_metadata_blocks(text)
    if options.max_text_chars and options.max_text_chars > 0 and len(text) > options.max_text_chars:
        text = text[: options.max_text_chars].rstrip() + f"\n\n… _truncated after {options.max_text_chars} characters_"
    return text.strip()


def _redact_metadata_blocks(text: str) -> str:
    patterns = [
        r"Conversation info \(untrusted metadata\):\n```json\n.*?\n```\n*",
        r"Sender \(untrusted metadata\):\n```json\n.*?\n```\n*",
        r"Replied message \(untrusted, for context\):\n```json\n.*?\n```\n*",
        r"\[message_id: [^\]]+\]\n?",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.DOTALL)
    return text.strip()


def _section(title: str, ts: str | None, body: str) -> list[str]:
    header = f"### {title}"
    if ts:
        header += f" · `{_escape_inline(str(ts))}`"
    return [header, "", body or "_empty_", ""]


def _usage_line(usage: dict[str, Any]) -> str:
    pieces = []
    for key in ("input", "output", "cacheRead", "cacheWrite", "total"):
        if key in usage:
            pieces.append(f"{key}={usage[key]}")
    return "> Usage: " + ", ".join(pieces)


def _json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n```"


def _render_index(rows: list[tuple[Path, SessionMeta]], out_dir: Path) -> str:
    lines = ["# OpenClaw session export", "", f"Generated files: {len(rows)}", ""]
    for path, meta in rows:
        rel = path.relative_to(out_dir)
        label = meta.started_at or meta.session_id or path.stem
        details = []
        if meta.model_id:
            details.append(meta.model_id)
        if meta.message_count:
            details.append(f"{meta.message_count} messages")
        suffix = f" — {', '.join(details)}" if details else ""
        lines.append(f"- [{_escape_inline(label)}]({rel.as_posix()}){suffix}")
    return "\n".join(lines) + "\n"


def _escape_inline(text: str) -> str:
    return text.replace("`", "\\`")


def _escape_url(text: str) -> str:
    return text.replace(")", "%29")
