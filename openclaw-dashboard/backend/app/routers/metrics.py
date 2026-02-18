"""Token usage and metrics endpoints.

Pulls usage data from agent gateways via RPC (sessions.usage), aggregates
across all agents, and falls back to cache-trace.jsonl parsing when gateways
are unreachable.
"""

import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Query

from app.services.gateway_rpc import gateway_call, AGENT_GATEWAYS
from app.services.cache_trace import analyze_token_usage, get_timeseries, get_breakdown

logger = logging.getLogger("metrics")
router = APIRouter(tags=["metrics"])


async def _gather_rpc_usage() -> dict:
    """Aggregate sessions.usage from all agent gateways.

    Returns a dict with:
      - by_model: [{model, provider, tokens, cost, requests, input, output}]
      - daily_trend: [{date, tokens, cost}]  (aggregated across models)
      - daily_model: [{date, model, provider, tokens, cost, count}]
      - totals: {input, output, totalTokens, totalCost, messages}
    """
    model_agg: dict[str, dict] = defaultdict(lambda: {
        "tokens": 0, "cost": 0.0, "requests": 0,
        "input": 0, "output": 0, "provider": "",
    })
    daily_agg: dict[str, dict] = defaultdict(lambda: {"tokens": 0, "cost": 0.0})
    daily_model_agg: dict[str, dict] = defaultdict(lambda: {
        "tokens": 0, "cost": 0.0, "count": 0, "provider": "", "model": "",
    })
    # Per-agent daily totals: keyed by "{date}|{agent_id}"
    agent_daily_agg: dict[str, dict] = defaultdict(lambda: {"tokens": 0, "cost": 0.0})
    totals = {"input": 0, "output": 0, "totalTokens": 0, "totalCost": 0.0, "messages": 0}

    for agent_id in AGENT_GATEWAYS:
        try:
            r = await gateway_call("sessions.usage", agent=agent_id, timeout=5)
            if not r.get("ok"):
                continue
            payload = r.get("result", r.get("payload", {}))

            # Aggregate totals
            t = payload.get("totals", {})
            totals["input"] += t.get("input", 0)
            totals["output"] += t.get("output", 0)
            totals["totalTokens"] += t.get("totalTokens", 0)
            totals["totalCost"] += t.get("totalCost", 0)
            agg = payload.get("aggregates", {})
            totals["messages"] += agg.get("messages", {}).get("total", 0)

            # Per-session data
            for sess in payload.get("sessions", []):
                usage = sess.get("usage", {})

                # Per-model usage from this session
                for mu in usage.get("modelUsage", []):
                    model = mu.get("model", "unknown")
                    provider = mu.get("provider", "unknown")
                    m_totals = mu.get("totals", {})
                    key = f"{provider}/{model}"
                    model_agg[key]["tokens"] += m_totals.get("totalTokens", 0)
                    model_agg[key]["cost"] += m_totals.get("totalCost", 0)
                    model_agg[key]["requests"] += mu.get("count", 0)
                    model_agg[key]["input"] += m_totals.get("input", 0)
                    model_agg[key]["output"] += m_totals.get("output", 0)
                    model_agg[key]["provider"] = provider

                # Daily breakdown (aggregated)
                for db in usage.get("dailyBreakdown", []):
                    date = db.get("date", "")
                    if date:
                        daily_agg[date]["tokens"] += db.get("tokens", 0)
                        daily_agg[date]["cost"] += db.get("cost", 0)
                        # Also track per-agent daily
                        ak = f"{date}|{agent_id}"
                        agent_daily_agg[ak]["tokens"] += db.get("tokens", 0)
                        agent_daily_agg[ak]["cost"] += db.get("cost", 0)

                # Daily model usage (per-model per-day)
                for dmu in usage.get("dailyModelUsage", []):
                    date = dmu.get("date", "")
                    model = dmu.get("model", "unknown")
                    provider = dmu.get("provider", "unknown")
                    key = f"{date}|{provider}/{model}"
                    daily_model_agg[key]["tokens"] += dmu.get("tokens", 0)
                    daily_model_agg[key]["cost"] += dmu.get("cost", 0)
                    daily_model_agg[key]["count"] += dmu.get("count", 0)
                    daily_model_agg[key]["provider"] = provider
                    daily_model_agg[key]["model"] = model

        except Exception as e:
            logger.debug("Failed to get usage from %s: %s", agent_id, e)

    by_model = sorted(
        [
            {
                "model": k.split("/", 1)[-1],
                "provider": v["provider"],
                "tokens": v["tokens"],
                "cost": round(v["cost"], 4),
                "requests": v["requests"],
                "input": v["input"],
                "output": v["output"],
            }
            for k, v in model_agg.items()
        ],
        key=lambda x: x["tokens"],
        reverse=True,
    )

    daily_trend = [
        {"date": k, "tokens": v["tokens"], "cost": round(v["cost"], 4)}
        for k, v in sorted(daily_agg.items())
    ]

    daily_model = [
        {
            "date": k.split("|")[0],
            "model": v["model"],
            "provider": v["provider"],
            "tokens": v["tokens"],
            "cost": round(v["cost"], 4),
            "count": v["count"],
        }
        for k, v in sorted(daily_model_agg.items())
    ]

    agent_daily = [
        {"date": k.split("|")[0], "agent": k.split("|")[1],
         "tokens": v["tokens"], "cost": round(v["cost"], 4)}
        for k, v in sorted(agent_daily_agg.items())
    ]

    return {
        "by_model": by_model,
        "daily_trend": daily_trend,
        "daily_model": daily_model,
        "agent_daily": agent_daily,
        "totals": totals,
    }


@router.get("/api/metrics/tokens")
async def token_metrics(days: int = Query(7, le=30)):
    # Try RPC first
    rpc = await _gather_rpc_usage()
    if rpc["by_model"]:
        return {
            "period_days": days,
            "models": rpc["by_model"],
            "total_tokens": rpc["totals"]["totalTokens"],
            "total_cost": round(rpc["totals"]["totalCost"], 2),
        }
    # Fallback to file-based
    metrics = analyze_token_usage(days=days)
    return {
        "period_days": days,
        "models": list(metrics.values()),
        "total_tokens": sum(m["input_tokens"] + m["output_tokens"] for m in metrics.values()),
        "total_cost": round(sum(m["cost"] for m in metrics.values()), 2),
    }


@router.get("/api/metrics/timeseries")
async def timeseries(metric: str = "tokens", hours: int = Query(24, le=168)):
    """Return per-model daily data for time-series charts.

    Response: {metric, models: [str], data: [{date, model_a: val, model_b: val, ...}]}
    """
    rpc = await _gather_rpc_usage()

    if rpc["daily_model"]:
        # Build a pivot table: date → {model: value}
        models: set[str] = set()
        pivot: dict[str, dict[str, float]] = defaultdict(dict)
        for entry in rpc["daily_model"]:
            date = entry["date"]
            model = entry["model"]
            models.add(model)
            val = entry["tokens"] if metric == "tokens" else entry["cost"]
            pivot[date][model] = pivot[date].get(model, 0) + val

        sorted_models = sorted(models)
        data = []
        for date in sorted(pivot.keys()):
            point: dict = {"label": date}
            for m in sorted_models:
                point[m] = pivot[date].get(m, 0)
            data.append(point)

        return {"metric": metric, "models": sorted_models, "data": data}

    # Fallback
    file_data = get_timeseries(metric=metric, hours=hours)
    return {"metric": metric, "models": [], "data": file_data}


@router.get("/api/metrics/breakdown")
async def breakdown():
    """Return by_model and daily_trend with per-model daily breakdown.

    Response includes:
      - by_model: [{model, tokens, cost, requests}]
      - daily_trend: [{date, tokens, cost}]
      - daily_model: [{date, model, tokens, cost, count}]
    """
    rpc = await _gather_rpc_usage()

    if rpc["by_model"]:
        return {
            "by_model": rpc["by_model"],
            "daily_trend": rpc["daily_trend"],
            "daily_model": rpc["daily_model"],
        }

    return get_breakdown()


@router.get("/api/metrics/timeseries/agents")
async def agent_timeseries(metric: str = "tokens", hours: int = Query(168, le=720)):
    """Return per-agent daily data for time-series charts.

    Response: {metric, agents: [str], data: [{label, agent_a: val, agent_b: val, ...}]}
    """
    rpc = await _gather_rpc_usage()

    agents: set[str] = set()
    pivot: dict[str, dict[str, float]] = defaultdict(dict)

    for entry in rpc.get("agent_daily", []):
        date = entry["date"]
        agent = entry["agent"]
        agents.add(agent)
        val = entry["tokens"] if metric == "tokens" else entry["cost"]
        pivot[date][agent] = pivot[date].get(agent, 0) + val

    sorted_agents = sorted(agents)
    data = []
    for date in sorted(pivot.keys()):
        point: dict = {"label": date}
        for a in sorted_agents:
            point[a] = pivot[date].get(a, 0)
        data.append(point)

    return {"metric": metric, "agents": sorted_agents, "data": data}
