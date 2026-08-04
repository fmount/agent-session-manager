"""Dynamic pricing fetcher for csm.

Resolves per-model token pricing from two sources:
1. OpenRouter API (per-model REST endpoint, no auth)
2. LiteLLM static JSON on GitHub (bulk fallback)

Results are cached locally for 24 hours at ~/.cache/csm/pricing.json.
"""

import json
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

CONFIG_DIR = Path.home() / ".config" / "csm"
CONFIG_PATH = CONFIG_DIR / "config.json"
CACHE_DIR = Path.home() / ".cache" / "csm"
CACHE_PATH = CACHE_DIR / "pricing.json"
CACHE_TTL = 86400  # 24 hours

OPENROUTER_MODEL_URL = "https://openrouter.ai/api/v1/model/"
LITELLM_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/"
    "main/model_prices_and_context_window.json"
)

PROVIDERS = {
    "openrouter": "_fetch_openrouter",
    "litellm": "_fetch_litellm",
}
DEFAULT_PROVIDER = "openrouter"


def _load_provider():
    """Read pricing_provider from ~/.config/csm/config.json."""
    if not CONFIG_PATH.exists():
        return DEFAULT_PROVIDER
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        return data.get("pricing_provider", DEFAULT_PROVIDER)
    except (json.JSONDecodeError, OSError):
        return DEFAULT_PROVIDER


def _per_token_to_per_million(val):
    return float(val) * 1_000_000


def _fetch_json(url, timeout=10):
    req = Request(url, headers={"User-Agent": "csm/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _openrouter_candidates(model):
    """Generate OpenRouter model ID candidates from a JSONL model name.

    OpenRouter uses "anthropic/<name>" where version separators may be
    dots instead of hyphens.  Rather than guessing the exact format, we
    try the name as-is first, then swap the last hyphen-digit boundary
    to a dot.

    Examples:
        "claude-opus-4-6"   -> "anthropic/claude-opus-4-6"    (try first)
                             -> "anthropic/claude-opus-4.6"    (dot variant)
        "claude-sonnet-4-6" -> "anthropic/claude-sonnet-4-6"
                             -> "anthropic/claude-sonnet-4.6"
        "claude-haiku-4-5-20251001"
                             -> "anthropic/claude-haiku-4-5-20251001" (as-is)
                                (no dot variant: last segment is not a
                                 bare digit)
    """
    yield f"anthropic/{model}"
    # replace last "-N" with ".N" only when the trailing segment is a bare digit
    i = model.rfind("-")
    if i > 0 and model[i + 1:].isdigit():
        yield f"anthropic/{model[:i]}.{model[i + 1:]}"


def _fetch_openrouter(models):
    """Fetch pricing from OpenRouter per-model API.

    Tries each candidate URL from _openrouter_candidates() until one
    returns valid pricing data.  Skips models that fail all candidates.

    Input:  {"claude-opus-4-6", "claude-sonnet-4-6"}
    Output: {"claude-opus-4-6": {"input": 5.0, "output": 25.0, ...}, ...}
    """
    pricing = {}
    for model in models:
        for candidate in _openrouter_candidates(model):
            url = OPENROUTER_MODEL_URL + candidate
            try:
                data = _fetch_json(url)
            except (URLError, OSError, json.JSONDecodeError, KeyError):
                continue

            p = data.get("data", {}).get("pricing", {})
            if p and p.get("prompt"):
                pricing[model] = {
                    "input": _per_token_to_per_million(p["prompt"]),
                    "output": _per_token_to_per_million(p["completion"]),
                    "cache_create": _per_token_to_per_million(
                        p.get("input_cache_write", 0)
                    ),
                    "cache_read": _per_token_to_per_million(
                        p.get("input_cache_read", 0)
                    ),
                }
                break
    return pricing if pricing else None


def _litellm_find(data, model):
    """Find a LiteLLM entry by substring match.

    LiteLLM keys have varying prefixes and suffixes:
        "anthropic.claude-opus-4-6-v1"
        "us.anthropic.claude-opus-4-7"
        "global.anthropic.claude-sonnet-4-6"

    Instead of guessing the exact key, we find entries whose key contains
    the JSONL model name, preferring the shortest match (least qualified,
    i.e. base pricing without region markup).

    Examples:
        model="claude-opus-4-6"
          matches: "anthropic.claude-opus-4-6-v1" (len 31),
                   "us.anthropic.claude-opus-4-6-v1" (len 34), ...
          returns: the entry for "anthropic.claude-opus-4-6-v1" (shortest)

        model="claude-sonnet-4-6"
          matches: "anthropic.claude-sonnet-4-6" (len 27),
                   "eu.anthropic.claude-sonnet-4-6" (len 30), ...
          returns: the entry for "anthropic.claude-sonnet-4-6" (shortest)
    """
    # filter to keys that contain the model name and have pricing data
    matches = [
        (k, v) for k, v in data.items()
        if model in k and isinstance(v, dict) and "input_cost_per_token" in v
    ]
    if not matches:
        return None
    # shortest key = least region/version qualifiers = base pricing
    matches.sort(key=lambda kv: len(kv[0]))
    return matches[0][1]


def _fetch_litellm(models):
    """Fetch pricing from LiteLLM bulk JSON (~2MB download).

    Downloads the full model_prices_and_context_window.json and uses
    _litellm_find() to locate each model by substring match.

    Input:  {"claude-opus-4-6", "claude-sonnet-4-6"}
    Output: {"claude-opus-4-6": {"input": 5.0, "output": 25.0, ...}, ...}
    """
    try:
        data = _fetch_json(LITELLM_URL, timeout=15)
    except (URLError, OSError, json.JSONDecodeError):
        return None

    pricing = {}
    for model in models:
        entry = _litellm_find(data, model)
        if not entry:
            continue

        pricing[model] = {
            "input": _per_token_to_per_million(entry["input_cost_per_token"]),
            "output": _per_token_to_per_million(entry["output_cost_per_token"]),
            "cache_create": _per_token_to_per_million(
                entry.get("cache_creation_input_token_cost", 0)
            ),
            "cache_read": _per_token_to_per_million(
                entry.get("cache_read_input_token_cost", 0)
            ),
        }
    return pricing if pricing else None


def _read_cache(models):
    """Read cached pricing if fresh and covers all requested models."""
    if not CACHE_PATH.exists():
        return None
    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if time.time() - cache.get("fetched_at", 0) > CACHE_TTL:
        return None

    cached_pricing = cache.get("pricing", {})
    if not all(m in cached_pricing for m in models):
        return None

    return cached_pricing


def _write_cache(pricing):
    """Write pricing to local cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = {"fetched_at": time.time(), "pricing": pricing}
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except OSError:
        pass


def get_pricing(models):
    """Fetch pricing for a set of model names (as found in session JSONL).

    Uses the provider from ~/.config/csm/config.json (default: openrouter),
    falls back to the other provider on failure.

    Returns dict {model: {input, output, cache_create, cache_read}} with
    per-1M-token USD values, or None on total failure.
    """
    if not models:
        return None

    cached = _read_cache(models)
    if cached:
        return cached

    primary = _load_provider()
    fetchers = [_fetch_openrouter, _fetch_litellm]
    if primary == "litellm":
        fetchers = [_fetch_litellm, _fetch_openrouter]

    pricing = None
    for fetch in fetchers:
        pricing = fetch(models)
        if pricing:
            break

    if pricing:
        _write_cache(pricing)

    return pricing
