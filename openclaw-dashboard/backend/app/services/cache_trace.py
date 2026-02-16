"""Streaming reader for cache-trace.jsonl files.

Strategy: Read the files ONCE on startup (last 10MB only per file — enough for
recent data), build all aggregates in a single pass, cache for 5 minutes. All
three endpoints (tokens, timeseries, breakdown) share the same parsed data.

Supports multi-agent workspaces: aggregates traces from the root logs/ dir
and from each workspace-*/logs/ directory.
"""

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from app.config import settings

# Shared cache — one parse feeds all endpoints
_parsed_entries: List[Dict] = []
_parse_time = 0.0
_PARSE_TTL = 300  # 5 minutes — no need to re-read constantly
_MAX_READ_BYTES = 10_000_000  # 10MB from end of file — covers recent data


def _get_trace_files() -> List[Path]:
    """Return all existing cache-trace.jsonl paths across workspaces."""
    candidates = [settings.openclaw_dir / "logs" / "cache-trace.jsonl"]
    try:
        for p in sorted(settings.openclaw_dir.glob("workspace-*/logs/cache-trace.jsonl")):
            candidates.append(p)
    except Exception:
        pass
    return [f for f in candidates if f.exists()]


def _cost_for_model(model_id: str, provider: str, inp: int, out: int) -> float:
    ml = model_id.lower()
    pl = provider.lower()
    if "kimi" in ml or "moonshot" in pl or "pony" in ml:
        return 0.0
    if "claude" in ml:
        return (inp * 0.003 + out * 0.015) / 1000
    if "gpt-4" in ml:
        return (inp * 0.03 + out * 0.06) / 1000
    return 0.0


def _parse_trace_file(trace_file: Path, agent_label: str) -> List[Dict]:
    """Parse a single trace file, returning entries with agent label."""
    entries = []
    try:
        file_size = trace_file.stat().st_size
        read_from = max(0, file_size - _MAX_READ_BYTES)

        with open(trace_file) as f:
            if read_from > 0:
                f.seek(read_from)
                f.readline()  # skip partial line

            for line in f:
                try:
                    entry = json.loads(line)
                    ts_str = entry.get("ts", "")
                    if not ts_str:
                        continue
                    entry["_ts"] = datetime.fromisoformat(
                        ts_str.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    entry["_agent"] = agent_label
                    entries.append(entry)
                except Exception:
                    continue
    except Exception:
        pass
    return entries


def _ensure_parsed():
    """Parse the tail of all trace files across workspaces. Cached for 5 min."""
    global _parsed_entries, _parse_time

    now = time.time()
    if _parsed_entries and now - _parse_time < _PARSE_TTL:
        return

    trace_files = _get_trace_files()
    if not trace_files:
        _parsed_entries = []
        _parse_time = now
        return

    entries = []
    for tf in trace_files:
        # Derive agent label from path: workspace-foo/logs/... -> "foo"
        parent_dir = tf.parent.parent.name
        if parent_dir.startswith("workspace-"):
            agent_label = parent_dir.replace("workspace-", "")
        else:
            agent_label = "default"
        entries.extend(_parse_trace_file(tf, agent_label))

    # Sort by timestamp for consistent ordering
    entries.sort(key=lambda e: e["_ts"])
    _parsed_entries = entries
    _parse_time = now


def analyze_token_usage(days: int = 1) -> Dict:
    _ensure_parsed()

    cutoff = datetime.now() - timedelta(days=days)
    model_stats: Dict = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
        "provider": "", "count": 0
    })

    for entry in _parsed_entries:
        if entry["_ts"] < cutoff:
            continue
        model_id = entry.get("modelId", "unknown")
        usage = entry.get("usage", {})
        stats = model_stats[model_id]
        stats["provider"] = entry.get("provider", "unknown")
        stats["input"] += usage.get("input", 0)
        stats["output"] += usage.get("output", 0)
        stats["cache_read"] += usage.get("cacheRead", 0)
        stats["cache_write"] += usage.get("cacheWrite", 0)
        stats["count"] += 1

    result = {}
    for model_id, stats in model_stats.items():
        cost = _cost_for_model(model_id, stats["provider"], stats["input"], stats["output"])
        result[model_id] = {
            "model": model_id,
            "provider": stats["provider"],
            "input_tokens": stats["input"],
            "output_tokens": stats["output"],
            "cost": cost,
            "cache_hits": stats["cache_read"],
            "cache_writes": stats["cache_write"],
            "requests": stats["count"],
        }
    return result


def get_timeseries(metric: str = "tokens", hours: int = 24) -> List[Dict]:
    _ensure_parsed()

    cutoff = datetime.now() - timedelta(hours=hours)
    buckets: Dict[str, Dict] = {}

    for entry in _parsed_entries:
        ts = entry["_ts"]
        if ts < cutoff:
            continue
        hour_key = ts.strftime("%H:00")
        if hour_key not in buckets:
            buckets[hour_key] = {"tokens": 0, "cost": 0.0, "requests": 0}
        usage = entry.get("usage", {})
        inp = usage.get("input", 0)
        out = usage.get("output", 0)
        buckets[hour_key]["tokens"] += inp + out
        buckets[hour_key]["cost"] += _cost_for_model(
            entry.get("modelId", ""), entry.get("provider", ""), inp, out
        )
        buckets[hour_key]["requests"] += 1

    return [
        {
            "timestamp": k,
            "value": b["tokens"] if metric == "tokens" else round(b["cost"], 4) if metric == "cost" else b["requests"],
            "label": k,
        }
        for k, b in sorted(buckets.items())
    ]


def get_breakdown() -> Dict:
    _ensure_parsed()

    cutoff = datetime.now() - timedelta(days=7)
    model_agg: Dict = defaultdict(lambda: {"tokens": 0, "cost": 0.0, "requests": 0})
    daily: Dict = defaultdict(lambda: {"tokens": 0, "cost": 0.0})

    for entry in _parsed_entries:
        ts = entry["_ts"]
        if ts < cutoff:
            continue
        usage = entry.get("usage", {})
        inp = usage.get("input", 0)
        out = usage.get("output", 0)
        model_id = entry.get("modelId", "unknown")
        cost = _cost_for_model(model_id, entry.get("provider", ""), inp, out)

        model_agg[model_id]["tokens"] += inp + out
        model_agg[model_id]["cost"] += cost
        model_agg[model_id]["requests"] += 1

        day_key = ts.strftime("%Y-%m-%d")
        daily[day_key]["tokens"] += inp + out
        daily[day_key]["cost"] += cost

    by_model = sorted(
        [{"model": k, "tokens": v["tokens"], "cost": round(v["cost"], 2), "requests": v["requests"]}
         for k, v in model_agg.items()],
        key=lambda x: x["tokens"], reverse=True,
    )
    daily_trend = [
        {"date": k, "tokens": v["tokens"], "cost": round(v["cost"], 2)}
        for k, v in sorted(daily.items())
    ]
    return {"by_model": by_model, "daily_trend": daily_trend}
