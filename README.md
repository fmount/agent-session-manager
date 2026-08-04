# csm — Agent Session Manager

Browse and resume AI coding agent sessions from any directory.

Currently supports **Claude Code**. Sessions are scattered across
`~/.claude/projects/` with one directory per working path — `csm` scans
them all, decodes the project slug back to a real filesystem path, and
lets you pick one via `fzf` to resume.

## Agent session comparison

| | Claude Code | OpenCode | Pi (pi.dev) |
|---|---|---|---|
| Storage | `~/.claude/projects/<slug>/*.jsonl` | SQLite `~/.local/share/opencode/opencode.db` | `~/.pi/agent/sessions/<slug>/*.jsonl` |
| Slug format | `-` replaces `/` and `_` | N/A (DB `directory` column) | `--` wraps path, preserves `_` |
| Resume | `claude --resume <id>` | `opencode -s <id>` | `pi --session <id>` |
| Delete | `claude project purge <path>` | `opencode session delete <id>` | rm session file |
| Session metadata | `ai-title` record in JSONL | `title` column in SQLite | JSONL (similar to Claude) |

## Requirements

- Python 3.8+
- [fzf](https://github.com/junegunn/fzf) (interactive picker)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (to resume sessions)

## Install

```bash
make install        # installs to ~/.local/bin/csm
make check          # verify dependencies
```

## Usage

```bash
csm                 # open fzf picker, select a session, resume it
csm manila          # pre-filter the picker to "manila"
csm -l              # plain text list (no fzf)
csm -l -n 10        # last 10 sessions
csm -p glance       # filter by project path
csm -a              # include orphaned sessions (deleted project dirs)
csm --clean         # pick projects to purge (fzf multi-select with TAB)
```

## How it works

1. Scans `~/.claude/projects/*/` for `.jsonl` session files
2. Parses `aiTitle` and first user message from each file
3. Decodes the project slug back to a filesystem path (DFS with
   underscore/hyphen variant matching)
4. Filters out orphaned sessions (project directory no longer exists)
   unless `--all` is passed
5. Pipes the list to `fzf` with a preview pane showing session details
6. On selection, `cd`s to the project directory and `exec`s
   `claude --resume <session-id>`

## Uninstall

```bash
make uninstall
```

## License

MIT
