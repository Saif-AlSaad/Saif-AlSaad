#!/usr/bin/env python3
"""Builds assets/report.svg (live stats card) and refreshes the 'recent work'
block in README.md. Standard library only. Runs inside GitHub Actions."""
import json, os, re, urllib.request, urllib.error
from datetime import datetime, timezone
from html import escape

USER = os.environ.get("GH_USER", "Saif-AlSaad")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
FONT = "'JetBrains Mono','SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace"
LANG_COLORS = {"JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5", "Java": "#b07219",
               "C": "#8a8a8a", "HTML": "#e34c26", "CSS": "#8b5cf6", "PLpgSQL": "#336790", "SQL": "#e38c00",
               "C++": "#f34b7d", "Shell": "#89e051", "Dart": "#00B4AB"}
FALLBACK = ["#38bdf8", "#2ee59d", "#ffc857", "#f472b6", "#a78bfa", "#fb923c"]


def api(path, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-report"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def contributions():
    if not TOKEN:
        return None
    q = """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions
    weeks{contributionDays{contributionCount date}}}}}}"""
    try:
        d = api("/graphql", {"query": q, "variables": {"u": USER}})
        cal = d["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        return cal["totalContributions"], [[day["contributionCount"] for day in w["contributionDays"]] for w in cal["weeks"]]
    except Exception as e:  # keep going without the heatmap
        print("contributions unavailable:", e)
        return None


def human(n):
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


def build_report(user, repos, langs, contrib):
    own = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in own)
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    W, pad = 900, 36
    H = 345 if contrib else 196
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Live build report for {USER}">',
           f'<title>Live build report — generated {datetime.now(timezone.utc):%Y-%m-%d}</title>',
           '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b1020"/><stop offset="1" stop-color="#101a33"/></linearGradient></defs>',
           f'<style>text{{font-family:{FONT};font-size:13px;fill:#7d8aa5}}.big{{font-size:34px;font-weight:800;fill:#e6edf7}}.lbl{{font-size:11px;letter-spacing:1.5px}}.hd{{fill:#38bdf8;font-weight:700}}.w{{fill:#e6edf7}}</style>',
           f'<rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/><rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="14" fill="none" stroke="#26314d"/>',
           f'<text x="{pad}" y="34" class="hd">▸ BUILD REPORT</text>',
           f'<text x="{W-pad}" y="34" text-anchor="end" style="font-size:11px">auto-generated · {datetime.now(timezone.utc):%d %b %Y}</text>']
    cells = [(len(own), "REPOS · TESTS RUN"), (stars, "STARS · APPROVALS"), (user["followers"], "FOLLOWERS · REVIEWERS")]
    for i, (v, label) in enumerate(cells):
        x = pad + i * 150
        out.append(f'<text x="{x}" y="86" class="big">{human(v)}</text><text x="{x}" y="106" class="lbl">{label.split(" · ")[0]}</text>')
    if contrib:
        out.append(f'<text x="{pad+450}" y="86" class="big">{human(contrib[0])}</text><text x="{pad+450}" y="106" class="lbl">CONTRIBUTIONS · 12 MO</text>')
    # language coverage bar
    by = 140
    out.append(f'<text x="{pad}" y="{by-8}" class="lbl">LANGUAGE COVERAGE</text>')
    out.append(f'<clipPath id="c"><rect x="{pad}" y="{by}" width="{W-2*pad}" height="10" rx="5"/></clipPath><g clip-path="url(#c)">')
    x, bar_w = pad, W - 2 * pad
    legend = []
    for i, (name, n) in enumerate(top):
        w = bar_w * n / total
        col = LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])
        out.append(f'<rect x="{x:.1f}" y="{by}" width="{w:.1f}" height="10" fill="{col}"/>')
        x += w
        legend.append((name, col, n / total))
    out.append('</g>')
    lx = pad
    for name, col, pct in legend:
        out.append(f'<circle cx="{lx+5}" cy="{by+30}" r="4.5" fill="{col}"/><text x="{lx+16}" y="{by+34}" class="w" style="font-size:12px">{escape(name)} <tspan style="fill:#7d8aa5">{pct*100:.0f}%</tspan></text>')
        lx += 20 + 8 * len(f"{name} {pct*100:.0f}%") + 14
    if contrib:
        weeks = contrib[1]
        hy = 218
        out.append(f'<text x="{pad}" y="{hy-10}" class="lbl">TEST RUN HISTORY · LAST 12 MONTHS</text>')
        mx = max((c for w in weeks for c in w), default=1) or 1
        pal = ["#151c2c", "#134e4a", "#0f766e", "#14b8a6", "#5eead4"]
        pitch = (W - 2 * pad) / 53
        cs, gap = pitch - 2.6, 2.6
        for wi, w in enumerate(weeks[-53:]):
            for di, c in enumerate(w):
                lvl = 0 if c == 0 else 1 + min(3, int(3 * (c - 1) / max(mx, 1) * 1.6))
                out.append(f'<rect x="{pad+wi*(cs+gap):.1f}" y="{hy+di*(cs+gap):.1f}" width="{cs}" height="{cs}" rx="3" fill="{pal[lvl]}"/>')
    out.append('</svg>')
    return "\n".join(out)


def recent_block(repos):
    rows = []
    for r in sorted((r for r in repos if not r["fork"] and r["name"].lower() != USER.lower()), key=lambda r: r["pushed_at"], reverse=True)[:5]:
        d = datetime.strptime(r["pushed_at"], "%Y-%m-%dT%H:%M:%SZ")
        desc = (r["description"] or "—").replace("|", "/")
        rows.append(f"| [`{r['name']}`]({r['html_url']}) | {desc} | {r['language'] or '—'} | {d:%d %b %Y} |")
    return "| Repo | What it is | Lang | Last push |\n|:--|:--|:--|:--|\n" + "\n".join(rows)


def main():
    user = api(f"/users/{USER}")
    repos = api(f"/users/{USER}/repos?per_page=100&sort=pushed&type=owner")
    langs = {}
    for r in [r for r in repos if not r["fork"]][:30]:
        try:
            for k, v in api(r["languages_url"]).items():
                langs[k] = langs.get(k, 0) + v
        except urllib.error.URLError:
            pass
    open("assets/report.svg", "w", encoding="utf-8").write(build_report(user, repos, langs, contributions()))
    md = open("README.md", encoding="utf-8").read()
    new = re.sub(r"(<!--RECENT:START-->\n).*?(\n<!--RECENT:END-->)", lambda m: m.group(1) + recent_block(repos) + m.group(2), md, flags=re.S)
    open("README.md", "w", encoding="utf-8").write(new)
    print("updated")


if __name__ == "__main__":
    main()
