"""Generate the SVG cards (light / dark) for the GitHub profile README.

Outputs: hero-*.svg, link-*.svg, about-*.svg, stack-*.svg, activity-*.svg, languages-*.svg

Usage:
    PROFILE_GH_TOKEN=... python scripts/generate.py [OUT_DIR]
    python scripts/generate.py --sample [OUT_DIR]   # preview with random data
"""

import json
from html import escape
import os
import random
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

USER = "Hii-Dev"
API = "https://api.github.com/graphql"
JST = timezone(timedelta(hours=9))

THEMES = {
    "light": {
        "bg": "#ffffff", "tile": "#f6f8fa", "border": "#d1d9e0", "grid": "#eaeef2",
        "fg": "#1f2328", "muted": "#59636e", "a1": "#4f46e5", "a2": "#c026d3",
        "kw": "#cf222e", "prop": "#0550ae", "str": "#0a3069",
    },
    "dark": {
        "bg": "#0d1117", "tile": "#151b23", "border": "#3d444d", "grid": "#212830",
        "fg": "#f0f6fc", "muted": "#9198a1", "a1": "#818cf8", "a2": "#e879f9",
        "kw": "#ff7b72", "prop": "#79c0ff", "str": "#a5d6ff",
    },
}

SANS = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'
MONO = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'
W, PAD = 840, 32


# ================================================================ data

def graphql(query: str) -> dict:
    token = os.environ.get("PROFILE_GH_TOKEN")
    if not token:
        sys.exit("PROFILE_GH_TOKEN is not set")
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)
    if "errors" in body:
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def fetch(today: date) -> tuple[dict[date, int], list[dict]]:
    """Return ({date: contributions}, [{name, color, size}]) for the user."""
    first = graphql(f"""{{ user(login: "{USER}") {{
      contributionsCollection {{ contributionYears }}
      repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {{
        nodes {{ languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
          edges {{ size node {{ name color }} }}
        }} }}
      }}
    }} }}""")

    langs: dict[str, dict] = {}
    for repo in first["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            entry = langs.setdefault(name, {"name": name, "color": edge["node"]["color"] or "#8b949e", "size": 0})
            entry["size"] += edge["size"]

    fields = "contributionCalendar { weeks { contributionDays { date contributionCount } } }"
    aliases = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") {{ {fields} }}'
        for y in first["contributionsCollection"]["contributionYears"]
    )
    days = {}
    for collection in graphql(f'{{ user(login: "{USER}") {{ {aliases} }} }}').values():
        for week in collection["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                day = date.fromisoformat(d["date"])
                if day <= today:
                    days[day] = d["contributionCount"]

    return days, sorted(langs.values(), key=lambda l: -l["size"])


def sample(today: date) -> tuple[dict[date, int], list[dict]]:
    rng = random.Random(42)
    start = date(today.year - 2, 1, 1)
    days = {}
    for n in range((today - start).days + 1):
        day = start + timedelta(n)
        busy = 1.6 + 1.2 * ((day.toordinal() // 45) % 3)
        days[day] = 0 if rng.random() < 0.25 else int(rng.expovariate(1 / busy)) + 1
    langs = [
        {"name": "TypeScript", "color": "#3178c6", "size": 520},
        {"name": "Python", "color": "#3572A5", "size": 260},
        {"name": "CSS", "color": "#663399", "size": 110},
        {"name": "JavaScript", "color": "#f1e05a", "size": 80},
        {"name": "HTML", "color": "#e34c26", "size": 60},
        {"name": "Shell", "color": "#89e051", "size": 15},
        {"name": "Dockerfile", "color": "#384d54", "size": 8},
    ]
    return days, langs


# ================================================================ stats

def streaks(days: dict[date, int], today: date) -> tuple[int, int]:
    longest = run = 0
    for day in sorted(days):
        run = run + 1 if days[day] else 0
        longest = max(longest, run)

    # Today without contributions yet doesn't break the current streak.
    cursor = today if days.get(today) else today - timedelta(1)
    current = 0
    while days.get(cursor):
        current += 1
        cursor -= timedelta(1)
    return current, longest


def weekly(days: dict[date, int], today: date, weeks: int = 52) -> list[tuple[date, int]]:
    """Contributions per 7-day window, oldest first, the last window ending today."""
    out = []
    for i in reversed(range(weeks)):
        end = today - timedelta(7 * i)
        out.append((end, sum(days.get(end - timedelta(k), 0) for k in range(7))))
    return out


# ================================================================ render helpers

def svg(height: int, label: str, body: str, c: dict, extra_css: str = "", width: int = W, inset: float = 0) -> str:
    label = escape(label)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{label}">
<title>{label}</title>
<defs>
  <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{c["a1"]}"/><stop offset="1" stop-color="{c["a2"]}"/>
  </linearGradient>
</defs>
<style>
  text {{ font-family: {SANS}; fill: {c["fg"]}; }}
  .heading {{ font-size: 14px; font-weight: 600; }}
  .muted {{ font-size: 12px; fill: {c["muted"]}; }}
  .small {{ font-size: 11px; }}
  .fade {{ animation: fade .8s ease-out both; }}
  @keyframes fade {{ from {{ opacity: 0; transform: translateY(4px); }} }}
  {extra_css}
  @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
</style>
<rect x="{inset + 0.5}" y="0.5" width="{width - 1 - 2 * inset}" height="{height - 1}" rx="14" fill="{c["bg"]}" stroke="{c["border"]}"/>
{body}
</svg>
"""


def header(title: str, note: str = "", x: float = PAD) -> str:
    note_el = f'<text x="{W - PAD}" y="44" class="muted small" text-anchor="end">{note}</text>' if note else ""
    return (
        f'<rect x="{x}" y="31" width="4" height="16" rx="2" fill="url(#accent)"/>'
        f'<text x="{x + 12}" y="44" class="heading">{title}</text>{note_el}'
    )


def smooth(points: list[tuple[float, float]], floor: float) -> str:
    """Catmull-Rom spline through points as an SVG path, clamped above `floor`."""
    d = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    for i in range(len(points) - 1):
        p0, p1, p2 = points[max(i - 1, 0)], points[i], points[i + 1]
        p3 = points[min(i + 2, len(points) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, min(p1[1] + (p2[1] - p0[1]) / 6, floor))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, min(p2[1] - (p3[1] - p1[1]) / 6, floor))
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


# ================================================================ cards

def render_hero(c: dict) -> str:
    h = 220
    code = [
        [("kw", "const "), ("fg", "hii"), ("muted", " = {")],
        [("prop", "  role"), ("muted", ": "), ("str", '"Programmer"'), ("muted", ",")],
        [("prop", "  base"), ("muted", ": "), ("str", '"Chiba, Japan"'), ("muted", ",")],
        [("prop", "  stack"), ("muted", ": ["), ("str", '"React"'), ("muted", ", "), ("str", '"FastAPI"'), ("muted", "],")],
        [("prop", "  loves"), ("muted", ": ["), ("str", '"beer"'), ("muted", ", "), ("str", '"books"'), ("muted", "],")],
        [("muted", "};")],
    ]
    cx, cy, cw, ch = 452, 34, 356, 152
    lines = "".join(
        f'<text x="{cx + 20}" y="{cy + 50 + i * 18}" xml:space="preserve" class="code fade" style="animation-delay:{0.3 + i * 0.08:.2f}s">'
        + "".join(f'<tspan fill="{c[k]}">{t}</tspan>' for k, t in line)
        + "</text>"
        for i, line in enumerate(code)
    )
    dots = "".join(
        f'<circle cx="{cx + 20 + i * 14}" cy="{cy + 18}" r="4" fill="{c["border"]}"/>' for i in range(3)
    )
    body = f"""
<defs>
  <pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse">
    <circle cx="1" cy="1" r="1" fill="{c["border"]}" opacity=".7"/>
  </pattern>
  <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="40"/></filter>
  <clipPath id="card"><rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="13"/></clipPath>
</defs>
<g clip-path="url(#card)">
  <rect width="{W}" height="{h}" fill="url(#dots)"/>
  <circle cx="120" cy="40" r="90" fill="{c["a1"]}" opacity=".22" filter="url(#blur)"/>
  <circle cx="340" cy="200" r="80" fill="{c["a2"]}" opacity=".16" filter="url(#blur)"/>
</g>
<text x="{PAD + 8}" y="84" class="muted fade" style="font-size:15px">Hi there, I'm</text>
<text x="{PAD + 4}" y="136" class="name fade" style="animation-delay:.1s">Hii</text>
<text x="{PAD + 8}" y="170" class="muted fade" style="font-size:15px;animation-delay:.2s">Programmer — Chiba, Japan</text>
<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="10" fill="{c["tile"]}" stroke="{c["border"]}" opacity=".96"/>
{dots}
{lines}
<rect x="{cx + 40}" y="{cy + 50 + 5 * 18 - 11}" width="7" height="14" fill="{c["a1"]}" class="cursor"/>
"""
    css = f"""
  .name {{ font-size: 56px; font-weight: 700; letter-spacing: -1.5px; fill: url(#accent); }}
  .code {{ font-family: {MONO}; font-size: 12.5px; white-space: pre; }}
  .cursor {{ animation: blink 1.1s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}"""
    return svg(h, "Hi there, I'm Hii — Programmer based in Chiba, Japan", body, c, css)


ABOUT = [
    ("Programmer", "Based in Chiba, Japan"),
    ("Building web apps", "React · FastAPI"),
    ("Beer & books", "Off the keyboard"),
]

EDUCATION = [
    ("Kawahara Computer Business College", "Graduated 2026"),
    ("Sanno University", "Graduated 2026"),
]

STACK = [  # (group, [(name, dot color or None for fg, optional note)])
    ("Frontend", [("TypeScript", "#3178c6"), ("React", "#61dafb"), ("Next.js", None), ("Tailwind CSS", "#38bdf8")]),
    ("Backend", [("Python", "#3572A5"), ("FastAPI", "#009688"), ("Java", "#b07219"), ("Spring Boot", "#6db33f")]),
    ("AI", [("Claude", "#d97757", "Claude Code"), ("ChatGPT", "#10a37f", "Codex")]),
    ("Other", [("Power Automate", "#0066ff")]),
]


def render_about(c: dict) -> str:
    mid = 432
    h = 70 + 50 * max(len(ABOUT), len(EDUCATION)) + 18

    def rows(items, x, delay):
        return "".join(
            f'<g class="fade" style="animation-delay:{delay + i * 0.08:.2f}s">'
            f'<text x="{x}" y="{70 + i * 50 + 16}" style="font-size:14px;font-weight:500">{escape(title)}</text>'
            f'<text x="{x}" y="{70 + i * 50 + 34}" class="muted">{escape(sub)}</text>'
            "</g>"
            for i, (title, sub) in enumerate(items)
        )

    body = f"""
{header("About")}
{rows(ABOUT, PAD, 0)}
<line x1="{mid}" y1="32" x2="{mid}" y2="{h - 32}" stroke="{c["grid"]}"/>
{header("Education", x=mid + 24)}
{rows(EDUCATION, mid + 24, 0.1)}
"""
    label = "About: " + "; ".join(f"{t} ({s})" for t, s in ABOUT + EDUCATION)
    return svg(h, label, body, c)


def render_stack(c: dict) -> str:
    x0, x1 = PAD + 112, W - PAD
    chips, y, n = "", 66, 0
    for group, items in STACK:
        chips += f'<text x="{PAD}" y="{y + 19}" class="muted small caps">{group}</text>'
        x = x0
        for name, color, *note in items:
            note = note[0] if note else ""
            w = len(name) * 7.4 + (len(note) * 6.6 + 8 if note else 0) + 42
            if x + w > x1:
                x, y = x0, y + 40
            note_el = f'<tspan class="muted" dx="6">{escape(note)}</tspan>' if note else ""
            chips += (
                f'<g class="fade" style="animation-delay:{n * 0.05:.2f}s">'
                f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="30" rx="15" fill="{c["tile"]}" stroke="{c["grid"]}"/>'
                f'<circle cx="{x + 17:.1f}" cy="{y + 15}" r="4.5" fill="{color or c["fg"]}"/>'
                f'<text x="{x + 29:.1f}" y="{y + 19.5}" style="font-size:13px">{escape(name)}{note_el}</text>'
                "</g>"
            )
            x += w + 8
            n += 1
        y += 44
    h = y + 18

    body = f"""
{header("Stack")}
{chips}
"""
    css = ".caps { text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }"
    label = "Stack: " + "; ".join(
        f"{g}: " + ", ".join(f"{i[0]} ({i[2]})" if len(i) > 2 else i[0] for i in items) for g, items in STACK
    )
    return svg(h, label, body, c, css)


def render_activity(days: dict[date, int], today: date, c: dict) -> str:
    h = 312
    year = sum(n for d, n in days.items() if d.year == today.year)
    total = sum(days.values())
    current, longest = streaks(days, today)

    tiles = [
        (f"{today.year}", f"{year:,}", ""),
        ("All time", f"{total:,}", ""),
        ("Current streak", f"{current}", "days"),
        ("Longest streak", f"{longest}", "days"),
    ]
    gap = 12
    tw = (W - 2 * PAD - gap * 3) / 4
    tile_svg = ""
    for i, (label, value, unit) in enumerate(tiles):
        x = PAD + i * (tw + gap)
        unit_el = f'<tspan class="unit" dx="5">{unit}</tspan>' if unit else ""
        tile_svg += (
            f'<g class="fade" style="animation-delay:{i * 0.08:.2f}s">'
            f'<rect x="{x:.1f}" y="66" width="{tw:.1f}" height="80" rx="10" fill="{c["tile"]}" stroke="{c["grid"]}"/>'
            f'<text x="{x + 18:.1f}" y="92" class="muted">{label}</text>'
            f'<text x="{x + 18:.1f}" y="128" class="value">{value}{unit_el}</text>'
            "</g>"
        )

    # weekly area chart
    series = weekly(days, today)
    top, bottom = 196, 266
    left, right = PAD, W - PAD
    peak = max(n for _, n in series) or 1
    step = (right - left) / (len(series) - 1)
    pts = [(left + i * step, bottom - (bottom - top) * n / peak) for i, (_, n) in enumerate(series)]
    line = smooth(pts, bottom)
    area = f"{line} L{right},{bottom} L{left},{bottom} Z"

    grid = "".join(
        f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{c["grid"]}" stroke-dasharray="3 4"/>'
        for y in (top, (top + bottom) / 2)
    ) + f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{c["grid"]}"/>'

    months, last_x, prev = "", -99.0, None
    for i, (end, _) in enumerate(series):
        start = end - timedelta(6)
        if prev is not None and start.month != prev and pts[i][0] - last_x > 44:
            months += f'<text x="{pts[i][0]:.1f}" y="{bottom + 20}" class="muted small" text-anchor="middle">{start:%b}</text>'
            last_x = pts[i][0]
        prev = start.month

    pi = max(range(len(series)), key=lambda i: series[i][1])
    px, py = pts[pi]
    anchor = "end" if px > right - 60 else "start" if px < left + 60 else "middle"
    peak_svg = (
        f'<g class="fade" style="animation-delay:1.2s">'
        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{c["bg"]}" stroke="url(#accent)" stroke-width="2"/>'
        f'<text x="{px:.1f}" y="{py - 10:.1f}" class="small" text-anchor="{anchor}" font-weight="600">{peak} / week</text>'
        "</g>"
    )

    body = f"""
<defs>
  <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{c["a1"]}" stop-opacity=".35"/>
    <stop offset="1" stop-color="{c["a2"]}" stop-opacity="0"/>
  </linearGradient>
</defs>
{header("Activity", f"Updated {today.isoformat()}")}
{tile_svg}
<text x="{PAD}" y="180" class="muted small">Weekly contributions · last 12 months</text>
{grid}
<path d="{area}" fill="url(#fill)" class="fade" style="animation-delay:.6s"/>
<path d="{line}" fill="none" stroke="url(#accent)" stroke-width="2.25" stroke-linecap="round" pathLength="1" class="draw"/>
{peak_svg}
{months}
"""
    css = f"""
  .value {{ font-size: 28px; font-weight: 650; letter-spacing: -0.5px; font-variant-numeric: tabular-nums; }}
  .unit {{ font-size: 13px; font-weight: 400; fill: {c["muted"]}; letter-spacing: 0; }}
  .draw {{ stroke-dasharray: 1; animation: draw 1.6s .3s ease-out both; }}
  @keyframes draw {{ from {{ stroke-dashoffset: 1; }} to {{ stroke-dashoffset: 0; }} }}"""
    label = (
        f"{year:,} contributions in {today.year}, {total:,} all time, "
        f"current streak {current} days, longest streak {longest} days"
    )
    return svg(h, label, body, c, css)


def render_languages(langs: list[dict], c: dict) -> str:
    top = langs[:6]
    rest = sum(l["size"] for l in langs[6:])
    if rest:
        top.append({"name": "Other", "color": c["border"], "size": rest})
    total = sum(l["size"] for l in top) or 1

    h = 64 + 30 + 24 * ((len(top) + 3) // 4) + 22
    bar_w = W - 2 * PAD
    segs, x = "", float(PAD)
    for l in top:
        w = bar_w * l["size"] / total
        segs += f'<rect x="{x:.1f}" y="66" width="{max(w - 2, 0):.1f}" height="10" fill="{l["color"]}"/>'
        x += w

    col_w = bar_w / 4
    legend = ""
    for i, l in enumerate(top):
        lx = PAD + (i % 4) * col_w
        ly = 112 + (i // 4) * 24
        legend += (
            f'<g class="fade" style="animation-delay:{0.3 + i * 0.05:.2f}s">'
            f'<circle cx="{lx + 5:.1f}" cy="{ly - 4}" r="5" fill="{l["color"]}"/>'
            f'<text x="{lx + 18:.1f}" y="{ly}" style="font-size:13px">{l["name"]}'
            f'<tspan class="muted" dx="6">{100 * l["size"] / total:.1f}%</tspan></text>'
            "</g>"
        )

    body = f"""
<defs><clipPath id="bar"><rect x="{PAD}" y="66" width="{bar_w}" height="10" rx="5"/></clipPath></defs>
{header("Languages", "by code size")}
<g clip-path="url(#bar)" class="grow">{segs}</g>
{legend}
"""
    css = """
  .grow { transform-origin: left; animation: grow 1s .1s cubic-bezier(.2,.8,.2,1) both; }
  @keyframes grow { from { transform: scaleX(0); } }"""
    label = "Top languages: " + ", ".join(f'{l["name"]} {100 * l["size"] / total:.0f}%' for l in top)
    return svg(h, label, body, c, css)


LINKS = [
    ("portfolio", "Portfolio", "hii-dev.vercel.app"),
    ("zenn", "Zenn", "zenn.dev/aputech"),
    ("note", "note", "note.com/h1idev"),
    ("x", "X", "@h1idev"),
]


GAP = 6  # ≈ the line gap (5–6px) GitHub leaves between stacked images


def render_link(title: str, sub: str, c: dict) -> str:
    """One quarter of the README width; the gap is baked in as side insets."""
    w, h, g = W // 4, 56, GAP / 2
    body = (
        f'<text x="{g + 18}" y="25" style="font-size:14px;font-weight:600">{escape(title)}</text>'
        f'<text x="{g + 18}" y="42" class="muted small">{escape(sub)}</text>'
        f'<path d="M{w - g - 27} 27 {w - g - 19} 19M{w - g - 25} 19h6v6" fill="none" stroke="url(#accent)" '
        'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    return svg(h, f"{title} — {sub}", body, c, width=w, inset=g)


# ================================================================ main

def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--sample"]
    out = Path(args[0] if args else "output")
    today = datetime.now(JST).date()

    days, langs = sample(today) if "--sample" in sys.argv else fetch(today)

    out.mkdir(parents=True, exist_ok=True)
    for name, c in THEMES.items():
        (out / f"hero-{name}.svg").write_text(render_hero(c), encoding="utf-8")
        for slug, title, sub in LINKS:
            (out / f"link-{slug}-{name}.svg").write_text(render_link(title, sub, c), encoding="utf-8")
        (out / f"about-{name}.svg").write_text(render_about(c), encoding="utf-8")
        (out / f"stack-{name}.svg").write_text(render_stack(c), encoding="utf-8")
        (out / f"activity-{name}.svg").write_text(render_activity(days, today, c), encoding="utf-8")
        (out / f"languages-{name}.svg").write_text(render_languages(langs, c), encoding="utf-8")
    print(f"Wrote hero / links / about / stack / activity / languages cards to {out}")


if __name__ == "__main__":
    main()
