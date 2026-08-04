"""Shared utilities for csm."""

import json
import os
import subprocess
import sys
from pathlib import Path


CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

DIM = "\033[2m"
BOLD = "\033[1m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def decode_slug(slug):
    """Decode a Claude project slug back to a filesystem path.

    Claude encodes the absolute working directory path by replacing every
    '/' *and* '_' with '-', producing slugs like '-home-user-my_proj'
    that map to '/home/user/my_proj'.  Because directory names themselves
    can contain hyphens, the mapping is ambiguous.  We resolve it with a
    DFS that validates each candidate segment against the real filesystem,
    trying both '-' and '_' variants at every join point.
    """
    raw = slug.lstrip("-")
    parts = raw.split("-")

    def _segment_variants(parts_slice):
        base = "-".join(parts_slice)
        yield base
        if len(parts_slice) > 1:
            yield "_".join(parts_slice)

    def _solve(idx, current):
        if idx == len(parts):
            return current if os.path.isdir(current) else None
        for end in range(idx + 1, len(parts) + 1):
            for segment in _segment_variants(parts[idx:end]):
                candidate = os.path.join(current, segment)
                if os.path.isdir(candidate):
                    result = _solve(end, candidate)
                    if result is not None:
                        return result
        return None

    result = _solve(0, "/")
    if result:
        return result

    def _greedy(idx, current):
        if idx == len(parts):
            return current
        for end in range(idx + 1, len(parts) + 1):
            segment = "-".join(parts[idx:end])
            candidate = os.path.join(current, segment)
            if end == len(parts):
                return candidate
            if os.path.isdir(candidate):
                return _greedy(end, candidate)
        return os.path.join(current, "-".join(parts[idx:]))

    return _greedy(0, "/")


def shorten_path(path):
    """Replace $HOME prefix with ~."""
    if not path:
        return "(unknown)"
    home = str(Path.home())
    if path == home:
        return "~"
    if path.startswith(home + "/"):
        return "~" + path[len(home):]
    return path


def extract_user_text(content, limit=200):
    """Extract text from a Claude JSONL user message content field."""
    if isinstance(content, str) and content.strip():
        return content.strip()[:limit]
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block["text"].strip()
                if text:
                    return text[:limit]
    return None


def parse_jsonl(jsonl_path, max_lines=150):
    """Parse a session JSONL file and return content metadata.

    Returns dict with: title, first_msg, user_turns, assistant_turns.
    Set max_lines=None to read the entire file (for preview).
    """
    title = None
    first_msg = None
    user_turns = 0
    assistant_turns = 0

    with open(jsonl_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_lines and i > max_lines:
                break
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if obj.get("type") == "ai-title" and not title:
                title = obj.get("aiTitle", "")
            if obj.get("role") == "user":
                user_turns += 1
                if not first_msg:
                    first_msg = extract_user_text(obj.get("content", ""))
            elif obj.get("role") == "assistant":
                assistant_turns += 1

    return {
        "title": title or "",
        "first_msg": first_msg or "",
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
    }


def run_fzf(cmd, fzf_input):
    """Run fzf with the given command and input. Returns selected output or None."""
    try:
        result = subprocess.run(cmd, input=fzf_input, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        print("Error: fzf is not installed.", file=sys.stderr)
        print("Install: pacman -S fzf / apt install fzf / brew install fzf", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0 or not result.stdout.strip():
        return None

    return result.stdout.strip()


def parse_jsonl_usage(jsonl_path):
    """Parse usage/token data from a session JSONL file.

    Deduplicates by message.id and excludes <synthetic> model records.
    """
    seen_ids = set()
    records = []

    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            if obj.get("type") != "assistant":
                continue

            msg = obj.get("message", {})
            msg_id = msg.get("id")
            if not msg_id or msg_id in seen_ids:
                continue
            seen_ids.add(msg_id)

            model = msg.get("model", "")
            if model == "<synthetic>":
                continue

            usage = msg.get("usage", {})
            if not usage:
                continue

            records.append({
                "model": model,
                "timestamp": obj.get("timestamp", ""),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
            })

    return records


def estimate_cost(records, pricing):
    """Estimate USD cost from usage records and a pricing dict. Returns None if no pricing."""
    if not pricing:
        return None
    total = 0.0
    for r in records:
        p = pricing.get(r["model"])
        if not p:
            continue
        total += r["input_tokens"] * p.get("input", 0) / 1_000_000
        total += r["output_tokens"] * p.get("output", 0) / 1_000_000
        total += r["cache_creation_input_tokens"] * p.get("cache_create", 0) / 1_000_000
        total += r["cache_read_input_tokens"] * p.get("cache_read", 0) / 1_000_000
    return total
