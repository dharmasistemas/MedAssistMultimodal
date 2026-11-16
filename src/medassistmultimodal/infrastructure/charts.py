"""Gráficos SVG determinísticos de métricas fornecidas, sem modelos ou datasets."""
from __future__ import annotations
import html
from pathlib import Path
from typing import Iterable

COLORS = ("#64748B", "#2563EB", "#F59E0B", "#0F766E")

def _svg_text(x: float, y: float, text: str, **attrs: object) -> str:
    """Cria um elemento de texto SVG com conteúdo escapado."""
    properties = " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in attrs.items())
    return f'<text x="{x}" y="{y}" {properties}>{html.escape(text)}</text>'

def write_grouped_chart(
    path: Path,
    rows: list[dict[str, object]],
    metrics: Iterable[tuple[str, str, str]],
    title: str,
    y_label: str,
    maximum: float,
) -> None:
    """Desenha barras agrupadas em SVG para métricas comparáveis."""
    width, height = 1000, 560
    left, top, right, bottom = 90, 75, 30, 130
    chart_width = width - left - right
    chart_height = height - top - bottom
    metrics = tuple(metrics)
    group_width = chart_width / len(rows)
    bar_width = min(46, group_width / (len(metrics) + 1))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        _svg_text(left, 35, title, font_family="Arial", font_size="22", font_weight="bold", fill="#172033"),
        _svg_text(left, 57, "Métricas fornecidas — geração determinística", font_family="Arial", font_size="13", fill="#475569"),
    ]
    for tick in range(6):
        value = maximum * tick / 5
        y = top + chart_height - chart_height * tick / 5
        parts.append(f'<line x1="{left}" y1="{y}" x2="{width-right}" y2="{y}" stroke="#E2E8F0" stroke-width="1"/>')
        parts.append(_svg_text(left - 12, y + 4, f"{value:.1f}", text_anchor="end", font_family="Arial", font_size="11", fill="#475569"))
    for group_index, row in enumerate(rows):
        center = left + group_width * (group_index + 0.5)
        total_bars = len(metrics) * bar_width
        start = center - total_bars / 2
        for metric_index, (field, label, color) in enumerate(metrics):
            value = float(row[field])
            bar_height = chart_height * value / maximum
            x = start + metric_index * bar_width
            y = top + chart_height - bar_height
            parts.append(f'<rect x="{x}" y="{y}" width="{bar_width-5}" height="{bar_height}" fill="{color}"/>')
            parts.append(_svg_text(x + (bar_width - 5) / 2, y - 7, f"{value:.3f}", text_anchor="middle", font_family="Arial", font_size="10", fill="#172033"))
        parts.append(_svg_text(center, top + chart_height + 25, str(row["label"]), text_anchor="middle", font_family="Arial", font_size="11", fill="#172033"))
    parts.append(_svg_text(22, top + chart_height / 2, y_label, transform=f"rotate(-90 22 {top + chart_height / 2})", text_anchor="middle", font_family="Arial", font_size="12", fill="#475569"))
    legend_x = left
    legend_y = height - 42
    for field, label, color in metrics:
        parts.append(f'<rect x="{legend_x}" y="{legend_y-12}" width="14" height="14" fill="{color}"/>')
        parts.append(_svg_text(legend_x + 21, legend_y, label, font_family="Arial", font_size="12", fill="#172033"))
        legend_x += 220
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")

def write_bar_chart(
    path: Path,
    rows: list[dict[str, object]],
    field: str,
    title: str,
    subtitle: str,
    unit: str,
) -> None:
    """Desenha um gráfico de barras SVG para uma métrica por categoria."""
    width, height = 1000, 540
    left, top, right, bottom = 100, 85, 35, 120
    chart_width = width - left - right
    chart_height = height - top - bottom
    values = [float(row[field]) for row in rows]
    maximum = max(values) * 1.15 if max(values) else 1.0
    group_width = chart_width / len(rows)
    bar_width = min(120, group_width * 0.55)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        _svg_text(left, 35, title, font_family="Arial", font_size="22", font_weight="bold", fill="#172033"),
        _svg_text(left, 58, subtitle, font_family="Arial", font_size="13", fill="#475569"),
    ]
    for tick in range(6):
        value = maximum * tick / 5
        y = top + chart_height - chart_height * tick / 5
        parts.append(f'<line x1="{left}" y1="{y}" x2="{width-right}" y2="{y}" stroke="#E2E8F0" stroke-width="1"/>')
        parts.append(_svg_text(left - 12, y + 4, f"{value:,.0f}", text_anchor="end", font_family="Arial", font_size="11", fill="#475569"))
    for index, (row, value) in enumerate(zip(rows, values)):
        center = left + group_width * (index + 0.5)
        bar_height = chart_height * value / maximum
        x = center - bar_width / 2
        y = top + chart_height - bar_height
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" fill="{COLORS[index]}"/>')
        parts.append(_svg_text(center, y - 9, f"{value:,.0f}", text_anchor="middle", font_family="Arial", font_size="12", font_weight="bold", fill="#172033"))
        parts.append(_svg_text(center, top + chart_height + 25, str(row["label"]), text_anchor="middle", font_family="Arial", font_size="11", fill="#172033"))
    parts.append(_svg_text(23, top + chart_height / 2, unit, transform=f"rotate(-90 23 {top + chart_height / 2})", text_anchor="middle", font_family="Arial", font_size="12", fill="#475569"))
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")
