"""Build a portable HTML dashboard without a web server."""

from __future__ import annotations

from html import escape
from pathlib import Path
import json
import math

import pandas as pd

from .data import DashboardConfig


def _safe(value: object) -> str:
    if pd.isna(value):
        return ""
    return escape(str(value))


def _number(value: float) -> str:
    if not math.isfinite(value):
        return "—"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _bars(labels: list[str], values: list[float]) -> str:
    if not values:
        return '<p class="empty">No valid values are available.</p>'
    highest = max(values) or 1
    rows = []
    for label, value in zip(labels, values):
        width = max(1, value / highest * 100) if value >= 0 else 1
        rows.append(
            f'<div class="bar-row"><span title="{escape(label)}">{escape(label)}</span>'
            f'<div class="track"><i style="width:{width:.2f}%"></i></div>'
            f'<strong>{_number(value)}</strong></div>'
        )
    return "".join(rows)


def build_dashboard(
    frame: pd.DataFrame,
    config: DashboardConfig,
    output: str | Path,
    title: str = "Public Health Dashboard",
) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows, columns = frame.shape
    missing = int(frame.isna().sum().sum())
    completeness = 100 * (1 - missing / max(1, rows * columns))

    total_value = float(frame[config.value].sum()) if config.value else float("nan")
    rate = float("nan")
    if config.value and config.population:
        population = float(frame[config.population].sum())
        if population > 0:
            rate = total_value / population * 100_000

    group_html = '<p class="empty">Choose a location or category column to see grouped totals.</p>'
    group_by = config.location or config.category
    if group_by and config.value:
        grouped = (
            frame.groupby(group_by, dropna=False)[config.value]
            .sum(min_count=1)
            .dropna()
            .sort_values(ascending=False)
            .head(15)
        )
        group_html = _bars([str(item) for item in grouped.index], grouped.astype(float).tolist())

    trend_html = '<p class="empty">Choose date and value columns to see a trend.</p>'
    if config.date and config.value:
        valid = frame.dropna(subset=[config.date, config.value]).copy()
        if not valid.empty:
            valid["_period"] = valid[config.date].dt.to_period("M").astype(str)
            trend = valid.groupby("_period")[config.value].sum().tail(18)
            trend_html = _bars(trend.index.tolist(), trend.astype(float).tolist())

    quality_rows = []
    for column in frame.columns:
        nulls = int(frame[column].isna().sum())
        unique = int(frame[column].nunique(dropna=True))
        quality_rows.append(
            f"<tr><td>{escape(column)}</td><td>{escape(str(frame[column].dtype))}</td>"
            f"<td>{nulls:,}</td><td>{unique:,}</td></tr>"
        )

    preview = frame.head(20)
    preview_head = "".join(f"<th>{escape(column)}</th>" for column in preview.columns)
    preview_rows = "".join(
        "<tr>" + "".join(f"<td>{_safe(value)}</td>" for value in row) + "</tr>"
        for row in preview.itertuples(index=False, name=None)
    )
    config_json = escape(json.dumps({key: value for key, value in config.__dict__.items() if value}))

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
:root{{--navy:#123047;--blue:#087e8b;--mint:#dff3ef;--ink:#17252d;--muted:#667780;--paper:#f5f8f8}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 system-ui,sans-serif}}
header{{padding:36px max(24px,6vw);color:white;background:linear-gradient(125deg,var(--navy),var(--blue))}}
header p{{margin:6px 0 0;color:#d4eded}} main{{max-width:1200px;margin:auto;padding:28px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}} .card,.panel{{background:white;border:1px solid #dce7e7;border-radius:14px;box-shadow:0 3px 14px #163b4810}}
.card{{padding:18px}} .card span{{color:var(--muted)}} .card strong{{display:block;font-size:25px;margin-top:5px;color:var(--navy)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(390px,1fr));gap:18px;margin-top:18px}} .panel{{padding:20px;overflow:auto}} h2{{font-size:18px;margin:0 0 17px}}
.bar-row{{display:grid;grid-template-columns:110px 1fr 75px;gap:10px;align-items:center;margin:10px 0}} .bar-row span{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}} .bar-row strong{{text-align:right}}
.track{{height:12px;background:#e8eeee;border-radius:20px;overflow:hidden}} .track i{{display:block;height:100%;background:var(--blue);border-radius:20px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{padding:9px 10px;border-bottom:1px solid #e5eded;text-align:left;white-space:nowrap}} th{{background:var(--mint);position:sticky;top:0}} .wide{{margin-top:18px}} .empty{{color:var(--muted)}} footer{{padding:20px;text-align:center;color:var(--muted)}}
@media(max-width:520px){{main{{padding:16px}}.grid{{grid-template-columns:1fr}}.bar-row{{grid-template-columns:80px 1fr 58px}}}}
</style></head><body>
<header><h1>{escape(title)}</h1><p>Generated from {rows:,} records · configuration: <code>{config_json}</code></p></header>
<main><section class="cards">
<div class="card"><span>Records</span><strong>{rows:,}</strong></div>
<div class="card"><span>Columns</span><strong>{columns:,}</strong></div>
<div class="card"><span>Completeness</span><strong>{completeness:.1f}%</strong></div>
<div class="card"><span>{escape(config.value or 'Selected value')}</span><strong>{_number(total_value)}</strong></div>
<div class="card"><span>Rate per 100,000</span><strong>{_number(rate)}</strong></div>
</section><section class="grid">
<article class="panel"><h2>{escape(config.value or 'Value')} by {escape(group_by or 'group')}</h2>{group_html}</article>
<article class="panel"><h2>Monthly trend</h2>{trend_html}</article>
</section><article class="panel wide"><h2>Data quality</h2><table><thead><tr><th>Column</th><th>Type</th><th>Missing</th><th>Unique</th></tr></thead><tbody>{''.join(quality_rows)}</tbody></table></article>
<article class="panel wide"><h2>Data preview (first 20 records)</h2><table><thead><tr>{preview_head}</tr></thead><tbody>{preview_rows}</tbody></table></article></main>
<footer>Generated by Public Health Framework</footer></body></html>"""
    output_path.write_text(html, encoding="utf-8")
    return output_path.resolve()

