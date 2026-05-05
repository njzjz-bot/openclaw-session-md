# openclaw-session-md

Convert OpenClaw session JSONL logs into readable Markdown transcripts.

The default input is the main-agent session directory:

```bash
~/.openclaw/agents/main/sessions
```

It understands both regular OpenClaw chat/checkpoint JSONL files and runtime trajectory JSONL files. By default directory conversion skips `*.trajectory.jsonl` and checkpoint snapshots to avoid exporting huge internal traces unless you explicitly ask for them.

## Install

From GitHub:

```bash
pipx install git+https://github.com/njzjz-bot/openclaw-session-md.git
# or
python -m pip install git+https://github.com/njzjz-bot/openclaw-session-md.git
```

For local development:

```bash
git clone https://github.com/njzjz-bot/openclaw-session-md.git
cd openclaw-session-md
python -m pip install -e .
```

## Usage

Convert one JSONL file to stdout:

```bash
openclaw-session-md ~/.openclaw/agents/main/sessions/<session>.jsonl
```

Convert one file to Markdown:

```bash
openclaw-session-md ~/.openclaw/agents/main/sessions/<session>.jsonl -o transcript.md
```

Convert the default session directory:

```bash
openclaw-session-md -o exported-sessions --index
```

Include runtime traces and checkpoint snapshots:

```bash
openclaw-session-md ~/.openclaw/agents/main/sessions \
  -o exported-sessions \
  --include-trajectory \
  --include-checkpoints \
  --index
```

Include full tool payloads:

```bash
openclaw-session-md <session.jsonl> --include-tools -o transcript.md
```

Strip common OpenClaw/channel metadata wrappers from user messages:

```bash
openclaw-session-md <session.jsonl> --redact-metadata -o transcript.md
```

List matching files without converting:

```bash
openclaw-session-md --list
```

## CLI options

- `input`: JSONL file or directory. Defaults to `~/.openclaw/agents/main/sessions`.
- `-o, --output`: output Markdown file or directory. Directory conversion requires an output directory.
- `--include-trajectory`: include `*.trajectory.jsonl` runtime trace files.
- `--include-checkpoints`: include `*.checkpoint.*.jsonl` files.
- `--include-tools`: render tool call/result payloads in expandable Markdown details blocks.
- `--redact-metadata`: remove common OpenClaw/channel metadata blocks embedded in messages.
- `--max-text-chars N`: truncate long message/tool payloads after `N` characters. Use `0` to disable truncation.
- `--index`: generate `index.md` when converting a directory.
- `--list`: print matching JSONL files and exit.

## Output style

The generated Markdown contains:

1. a session title;
2. metadata such as source file, session id, model, timestamps, and event counts;
3. a transcript/timeline with user and assistant messages;
4. optional tool details.

The converter is intentionally dependency-free and forgiving: malformed JSONL lines are rendered as parse-error blocks instead of crashing the whole export.

## Privacy note

OpenClaw logs can contain private messages, prompts, tool outputs, file paths, and service metadata. Review generated Markdown before publishing or sharing it.

## License

MIT
