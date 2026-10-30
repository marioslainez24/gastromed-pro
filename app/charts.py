"""Gráficas de tendencia en SVG generadas en el servidor (sin bibliotecas externas ni JavaScript)."""
from xml.sax.saxutils import escape


def trend_svg(points, ref_low=None, ref_high=None, unit="", width=640, height=220, title=""):
    """points: lista de (etiqueta_fecha, valor, marca) ordenada por fecha. Devuelve SVG accesible."""
    pts = [(d, float(v), f) for d, v, f in points if v is not None]
    if not pts:
        return ""
    pad_l, pad_r, pad_t, pad_b = 52, 16, 14, 34
    vals = [v for _, v, _ in pts] + [x for x in (ref_low, ref_high) if x is not None]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    span = hi - lo
    lo, hi = lo - span * 0.1, hi + span * 0.1
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    n = len(pts)

    def x(i):
        return pad_l + (w / 2 if n == 1 else i * w / (n - 1))

    def y(v):
        return pad_t + h - (v - lo) / (hi - lo) * h

    parts = [f'<svg class="trend" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}: '
             f'{escape(", ".join(f"{d} {v:g}" for d, v, _ in pts))}">']
    if ref_low is not None and ref_high is not None:
        parts.append(f'<rect class="trend-ref" x="{pad_l}" y="{y(ref_high):.1f}" width="{w}" height="{max(y(ref_low) - y(ref_high), 1):.1f}"/>')
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        parts.append(f'<line class="trend-grid" x1="{pad_l}" x2="{pad_l + w}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
        parts.append(f'<text class="trend-axis" x="{pad_l - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v:.3g}</text>')
    if n > 1:
        parts.append('<polyline class="trend-line" points="' + " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v, _) in enumerate(pts)) + '"/>')
    for i, (d, v, flag) in enumerate(pts):
        cls = "trend-dot" + (" is-out" if flag in ("alto", "bajo") else "")
        parts.append(f'<circle class="{cls}" cx="{x(i):.1f}" cy="{y(v):.1f}" r="4.5"><title>{escape(d)}: {v:g} {escape(unit)}</title></circle>')
        if n <= 12 or i in (0, n - 1) or i % max(1, n // 6) == 0:
            parts.append(f'<text class="trend-axis" x="{x(i):.1f}" y="{height - 10}" text-anchor="middle">{escape(d)}</text>')
    parts.append("</svg>")
    return "".join(parts)
