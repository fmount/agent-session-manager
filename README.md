# csm - Agent Session Manager

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
csm --stats              # monthly usage summary with cost estimates
csm --stats -p glance    # stats for a single project
csm --stats -m 2026-07   # stats for a single month
csm --stats -m 2026-07 -p glance  # combine both filters
```

## Stats examples

```
$ csm --stats
Month       Sessions   Turns   Input Tokens   Output Tokens     Cache Read   Est. Cost
─────────── ────────  ──────  ─────────────  ──────────────  ─────────────   ─────────
2026-08           12     406          3,448         122,343     36,609,975   $   40.78
2026-07           91    1738         17,359         738,180    129,342,771   $  173.16
2026-06            2     155            526          74,304     19,666,609   $   29.42
                                                                         ─────────
                                                                  Total: $  243.36

$ csm --stats -p glance
Month       Sessions   Turns   Input Tokens   Output Tokens     Cache Read   Est. Cost
─────────── ────────  ──────  ─────────────  ──────────────  ─────────────   ─────────
2026-08            1      52             70          15,086      4,193,177   $    4.08
2026-07            1      33             53           6,837      1,838,442   $    3.12
                                                                         ─────────
                                                                  Total: $    7.20

$ csm --stats -p manila
Month       Sessions   Turns   Input Tokens   Output Tokens     Cache Read   Est. Cost
─────────── ────────  ──────  ─────────────  ──────────────  ─────────────   ─────────
2026-07            3     114            583          33,635      8,244,444   $    6.99
                                                                         ─────────
                                                                  Total: $    6.99
```

Pricing is fetched dynamically from [OpenRouter](https://openrouter.ai/docs/guides/overview/models)
(primary) or [LiteLLM](https://github.com/BerriAI/litellm) (fallback) and cached
locally for 24 hours. Configure the provider in `~/.config/csm/config.json`:

```json
{"pricing_provider": "openrouter"}
```

## Statusline integration

Extract the current month's summary into a compact string for tmux,
polybar, waybar, i3status, or any shell prompt:

```bash
# one-liner: "csm: 12 sess | 434 turns | $44.18"
csm --stats -m "$(date +%Y-%m)" 2>/dev/null \
  | awk '/^[0-9]{4}-[0-9]{2}/ {printf "csm: %s sess | %s turns | %s\n", $2, $3, $NF}'
```

**tmux** — add to `~/.tmux.conf`:

```tmux
set -g status-right '#(csm --stats -m "$(date +%%Y-%%m)" 2>/dev/null | awk "/^[0-9]/{printf \"%%s sess | %%s turns | %%s\", \$2, \$3, \$NF}")'
set -g status-interval 300
```

**shell prompt (bash/zsh)** — add to `~/.bashrc` or `~/.zshrc`:

```bash
csm_prompt() {
  csm --stats -m "$(date +%Y-%m)" 2>/dev/null \
    | awk '/^[0-9]{4}-[0-9]{2}/ {printf "%s sess | %s", $2, $NF}'
}
# bash: PS1='[\u@\h \W $(csm_prompt)]\$ '
# zsh:  RPROMPT='$(csm_prompt)'
```

The pricing cache (24h TTL) keeps these fast — no network call on every
prompt refresh.

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
