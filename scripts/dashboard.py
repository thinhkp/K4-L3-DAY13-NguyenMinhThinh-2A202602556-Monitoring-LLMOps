from __future__ import annotations

import html
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
HOST = "127.0.0.1"
PORT = 8050
COLORS = {"p50": "#2563eb", "p95": "#dc2626", "p99": "#7c3aed", "ttft_p95": "#0891b2", "traffic": "#2563eb", "error_rate_pct": "#dc2626", "tool_success_rate_pct": "#059669", "cost_usd": "#d97706", "tokens_in": "#2563eb", "tokens_out": "#7c3aed", "quality_score": "#059669"}


def read_records() -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            record["_datetime"] = timestamp.astimezone(timezone.utc)
            if record["_datetime"] >= cutoff:
                records.append(record)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return records


def percentile(values: list[float], percent: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
    return ordered[rank]


def minute_key(record: dict[str, Any]) -> datetime:
    value = record["_datetime"]
    return value.replace(second=0, microsecond=0)


def bucket(records: list[dict[str, Any]], event: str, field: str | None = None) -> dict[datetime, list[float]]:
    result: dict[datetime, list[float]] = defaultdict(list)
    for record in records:
        if record.get("event") != event:
            continue
        value = record.get(field) if field else 1
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[minute_key(record)].append(float(value))
    return result


def series_for(panel_id: str, records: list[dict[str, Any]]) -> tuple[dict[str, dict[datetime, float]], dict[str, float | None]]:
    received = bucket(records, "request_received")
    responses = [row for row in records if row.get("event") == "response_sent"]
    failed = [row for row in records if row.get("event") == "request_failed"]
    if panel_id == "latency":
        latency = bucket(records, "response_sent", "latency_ms")
        ttft = bucket(records, "response_sent", "ttft_ms")
        return ({
            "p50": {key: percentile(values, 50) for key, values in latency.items()},
            "p95": {key: percentile(values, 95) for key, values in latency.items()},
            "p99": {key: percentile(values, 99) for key, values in latency.items()},
            "ttft_p95": {key: percentile(values, 95) for key, values in ttft.items()},
        }, {
            "P50": percentile([row["latency_ms"] for row in responses if isinstance(row.get("latency_ms"), (int, float))], 50),
            "P95": percentile([row["latency_ms"] for row in responses if isinstance(row.get("latency_ms"), (int, float))], 95),
            "P99": percentile([row["latency_ms"] for row in responses if isinstance(row.get("latency_ms"), (int, float))], 99),
            "TTFT P95": percentile([row["ttft_ms"] for row in responses if isinstance(row.get("ttft_ms"), (int, float))], 95),
        })
    if panel_id == "traffic":
        return ({"traffic": {key: float(len(values)) for key, values in received.items()}}, {"Requests": float(sum(map(len, received.values()))), "Rate": float(sum(map(len, received.values()))) / 60})
    if panel_id == "errors":
        requests_by_minute = {key: len(values) for key, values in received.items()}
        failed_by_minute: dict[datetime, int] = defaultdict(int)
        success_by_minute: dict[datetime, list[bool]] = defaultdict(list)
        for row in failed + responses:
            key = minute_key(row)
            if row.get("event") == "request_failed":
                failed_by_minute[key] += 1
            if isinstance(row.get("tool_success"), bool):
                success_by_minute[key].append(row["tool_success"])
        keys = set(requests_by_minute) | set(failed_by_minute) | set(success_by_minute)
        error_rate = {key: 100 * failed_by_minute[key] / requests_by_minute[key] if requests_by_minute.get(key) else 0.0 for key in keys}
        retrieval = {key: 100 * sum(success_by_minute[key]) / len(success_by_minute[key]) for key in keys if success_by_minute[key]}
        attempts = [row for row in failed + responses if isinstance(row.get("tool_success"), bool)]
        success_total = sum(row["tool_success"] for row in attempts)
        failures_by_type: dict[str, int] = defaultdict(int)
        for row in failed:
            failures_by_type[str(row.get("error_type", "unknown"))] += 1
        return ({"error_rate_pct": error_rate, "tool_success_rate_pct": retrieval}, {
            "Error rate": 100 * len(failed) / len(received) if received else None,
            "Retrieval success": 100 * success_total / len(attempts) if attempts else None,
            "Failed requests": float(len(failed)),
        } | {f"Error: {name}": float(count) for name, count in failures_by_type.items()})
    if panel_id == "cost":
        costs = bucket(records, "response_sent", "cost_usd")
        return ({"cost_usd": {key: sum(values) for key, values in costs.items()}}, {"Total": sum(row.get("cost_usd", 0) for row in responses if isinstance(row.get("cost_usd"), (int, float)))})
    if panel_id == "tokens":
        input_tokens = bucket(records, "response_sent", "tokens_in")
        output_tokens = bucket(records, "response_sent", "tokens_out")
        return ({"tokens_in": {key: sum(values) for key, values in input_tokens.items()}, "tokens_out": {key: sum(values) for key, values in output_tokens.items()}}, {
            "Input": sum(row.get("tokens_in", 0) for row in responses if isinstance(row.get("tokens_in"), (int, float))),
            "Output": sum(row.get("tokens_out", 0) for row in responses if isinstance(row.get("tokens_out"), (int, float))),
        })
    quality = bucket(records, "response_sent", "quality_score")
    all_scores = [value for values in quality.values() for value in values]
    return ({"quality_score": {key: sum(values) / len(values) for key, values in quality.items()}}, {
        "Average": sum(all_scores) / len(all_scores) if all_scores else None,
    })


def chart_svg(series: dict[str, dict[datetime, float]], threshold: float | None, unit: str) -> str:
    width, height, left, right, top, bottom = 720, 190, 52, 14, 12, 28
    plot_w, plot_h = width - left - right, height - top - bottom
    keys = sorted({point for values in series.values() for point in values})
    all_values = [value for values in series.values() for value in values.values()]
    if not keys:
        return f'<div class="empty">Chưa có dữ liệu trong cửa sổ 60 phút.</div>'
    ceiling = max([threshold or 0, *all_values, 1]) * 1.12
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Biểu đồ {html.escape(unit)}">']
    for tick in range(4):
        y = top + plot_h * tick / 3
        value = ceiling * (3 - tick) / 3
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid"/><text x="{left-7}" y="{y+4:.1f}" text-anchor="end" class="axis">{value:.1f}</text>')
    if threshold is not None:
        y = top + plot_h * (1 - threshold / ceiling)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="threshold"/><text x="{width-right-4}" y="{y-4:.1f}" text-anchor="end" class="threshold-label">limit {threshold:g}</text>')
    for name, values in series.items():
        points = []
        for index, key in enumerate(keys):
            if key not in values:
                continue
            x = left + (plot_w * index / max(1, len(keys) - 1))
            y = top + plot_h * (1 - values[key] / ceiling)
            points.append(f'{x:.1f},{y:.1f}')
        if points:
            parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{COLORS.get(name, "#2563eb")}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append(f'<text x="{left}" y="{height-6}" class="axis">{keys[0].strftime("%H:%M UTC")}</text><text x="{width-right}" y="{height-6}" text-anchor="end" class="axis">{keys[-1].strftime("%H:%M UTC")}</text></svg>')
    return "".join(parts)


def render_dashboard() -> str:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    records = read_records()
    panels_html = []
    for panel in config["panels"]:
        panel_id = panel["id"]
        series, summary = series_for(panel_id, records)
        threshold = panel["threshold"]
        stats = "".join(
            f'<div class="stat"><span>{html.escape(label)}</span><strong>{"—" if value is None else f"{value:.2f}"} {html.escape(panel["unit"])}</strong></div>'
            for label, value in summary.items()
        )
        legends = "".join(
            f'<span><i style="background:{COLORS.get(name, "#2563eb")}"></i>{html.escape(name)}</span>'
            for name in series
        )
        chart_threshold = float(threshold["value"]) if threshold["aggregation"] in series else None
        chart = chart_svg(series, chart_threshold, panel["unit"])
        panels_html.append(
            f'<section class="panel"><div class="panel-head"><div><h2>{html.escape(panel["title"])}</h2><p>{html.escape(panel_id)} · {html.escape(panel["unit"])} · last {config["time_range_minutes"]} min</p></div><b>{html.escape(threshold["aggregation"])} {html.escape(threshold["operator"])} {threshold["value"]} {html.escape(panel["unit"])}</b></div><div class="stats">{stats}</div><div class="chart">{chart}</div><div class="legend">{legends}</div></section>'
        )
    refreshed = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="{config["refresh_seconds"]}"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(config["title"])}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f1f5f9;color:#0f172a;font:14px/1.45 Segoe UI,Arial,sans-serif}}header{{padding:24px max(24px,calc((100vw - 1500px)/2));background:#0f172a;color:white;display:flex;justify-content:space-between;align-items:center;gap:20px}}h1{{font-size:22px;margin:0}}header p{{margin:5px 0 0;color:#cbd5e1}}main{{max-width:1548px;margin:auto;padding:20px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}.panel{{background:white;border:1px solid #dbe3ee;border-radius:12px;padding:17px;box-shadow:0 3px 12px #0f172a0a;min-width:0}}.panel-head{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}h2{{font-size:16px;margin:0 0 3px}}.panel-head p{{color:#64748b;margin:0;font-size:12px}}.panel-head b{{font-size:11px;color:#475569;background:#f8fafc;border:1px solid #e2e8f0;padding:5px 8px;border-radius:6px;white-space:nowrap}}.stats{{display:flex;gap:18px;flex-wrap:wrap;margin:15px 0 6px}}.stat span{{display:block;color:#64748b;font-size:11px}}.stat strong{{font-size:16px;font-variant-numeric:tabular-nums}}.chart svg{{width:100%;height:auto;display:block}}.grid{{stroke:#e2e8f0;stroke-width:1}}.axis{{fill:#64748b;font-size:10px}}.threshold{{stroke:#f59e0b;stroke-dasharray:5 4;stroke-width:1.5}}.threshold-label{{fill:#b45309;font-size:10px}}.legend{{display:flex;gap:14px;color:#475569;font-size:11px}}.legend i{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}}.empty{{height:190px;display:grid;place-items:center;color:#94a3b8}}footer{{max-width:1548px;margin:auto;padding:0 20px 22px;color:#64748b;font-size:12px}}@media(max-width:850px){{main{{grid-template-columns:1fr}}header{{align-items:flex-start;flex-direction:column}}}}
</style></head><body><header><div><h1>{html.escape(config["title"])}</h1><p>Runtime dashboard · source: data/logs.jsonl · rolling 60-minute window · refresh every {config["refresh_seconds"]} seconds</p></div><div>Updated {refreshed}<br>Requests in window: {sum(1 for row in records if row.get("event") == "request_received")}</div></header><main>{''.join(panels_html)}</main><footer>Metrics are calculated from application JSONL logs. Thresholds come from config/dashboard.yaml. Times are shown in UTC.</footer></body></html>'''


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        content = render_dashboard().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"dashboard: {format % args}")


def main() -> None:
    print(f"Dashboard ready at http://{HOST}:{PORT} (refreshes every 30 seconds)")
    ThreadingHTTPServer((HOST, PORT), DashboardHandler).serve_forever()


if __name__ == "__main__":
    main()
