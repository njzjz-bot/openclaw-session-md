from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from .converter import ConvertOptions, convert_path, find_session_files


# Avoid noisy "Exception ignored ... BrokenPipeError" when piping to tools like `head`.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def build_parser() -> argparse.ArgumentParser:
    default_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    parser = argparse.ArgumentParser(
        prog="openclaw-session-md",
        description="Convert OpenClaw session JSONL logs into readable Markdown transcripts.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(default_dir),
        help=f"JSONL file or directory to convert (default: {default_dir})",
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output Markdown file or directory. If input is a directory, this must be a directory. "
            "Use '-' to write a single file conversion to stdout."
        ),
    )
    parser.add_argument(
        "--include-trajectory",
        action="store_true",
        help="Also convert *.trajectory.jsonl runtime traces (default: only chat/checkpoint JSONL files).",
    )
    parser.add_argument(
        "--include-checkpoints",
        action="store_true",
        help="Include *.checkpoint.*.jsonl files when converting a directory.",
    )
    parser.add_argument(
        "--include-tools",
        action="store_true",
        help="Include tool call/result details. By default they are summarized or omitted.",
    )
    parser.add_argument(
        "--redact-metadata",
        action="store_true",
        help="Remove common OpenClaw/channel metadata blocks from user messages.",
    )
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=6000,
        help="Maximum characters per message/tool payload before truncation (default: 6000; <=0 disables).",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="When converting a directory, also write index.md with links and basic metadata.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List matching JSONL files and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser()
    options = ConvertOptions(
        include_tools=args.include_tools,
        redact_metadata=args.redact_metadata,
        max_text_chars=args.max_text_chars,
    )

    if args.list:
        for path in find_session_files(
            input_path,
            include_trajectory=args.include_trajectory,
            include_checkpoints=args.include_checkpoints,
        ):
            print(path)
        return 0

    try:
        outputs = convert_path(
            input_path,
            output=args.output,
            options=options,
            include_trajectory=args.include_trajectory,
            include_checkpoints=args.include_checkpoints,
            write_index=args.index,
        )
    except Exception as exc:  # pragma: no cover - exercised by CLI users
        print(f"openclaw-session-md: error: {exc}", file=sys.stderr)
        return 1

    if outputs:
        for out in outputs:
            print(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
