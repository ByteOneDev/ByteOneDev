#!/usr/bin/env python3
"""Génère les widgets SVG du profil (bannière, échecs, cartes projets).

Aucune dépendance externe : stdlib uniquement. Les widgets sont écrits en deux
variantes (dark / light) dans assets/, et le README les sélectionne via <picture>.
Toute erreur réseau est absorbée : on produit un widget dégradé plutôt qu'un
fichier manquant, pour ne jamais casser l'affichage du profil.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CONFIG = json.loads((ROOT / "widgets.config.json").read_text(encoding="utf-8"))

UA = "Mozilla/5.0 (compatible; profile-widgets/1.0; +https://github.com/ByteOneDev)"

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "panel": "#161b22",
        "border": "#30363d",
        "text": "#e6edf3",
        "muted": "#8b949e",
        "accent": "#58a6ff",
        "accent2": "#a371f7",
        "good": "#3fb950",
        "warn": "#d29922",
        "track": "#21262d",
    },
    "light": {
        "bg": "#ffffff",
        "panel": "#f6f8fa",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#59636e",
        "accent": "#0969da",
        "accent2": "#8250df",
        "good": "#1a7f37",
        "warn": "#9a6700",
        "track": "#eaeef2",
    },
}

LANG_COLORS = {
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Python": "#3572A5",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "C++": "#f34b7d",
    "C": "#555555",
    "Java": "#b07219",
    "Shell": "#89e051",
    "Rust": "#dea584",
    "Go": "#00ADD8",
}


def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        print(f"  ! échec {url} : {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Récupération des données
# --------------------------------------------------------------------------- #

CHESS_LABELS = {
    "bullet": "Bullet",
    "blitz": "Blitz",
    "rapid": "Rapide",
    "classical": "Classique",
    "puzzle": "Puzzles",
}


def fetch_lichess(username):
    """Retourne [(discipline, elo, parties, progression), ...] trié par nb de parties."""
    if not username:
        return None
    data = fetch_json(f"https://lichess.org/api/user/{username}")
    if not data or "perfs" not in data:
        return None
    rows = []
    for key in ("bullet", "blitz", "rapid", "classical", "puzzle"):
        perf = data["perfs"].get(key)
        if not perf or not perf.get("games") and key != "puzzle":
            continue
        rating = perf.get("rating")
        if not rating:
            continue
        rows.append(
            {
                "label": CHESS_LABELS[key],
                "rating": rating,
                "games": perf.get("games", 0) or perf.get("runs", 0),
                "prog": perf.get("prog", 0),
                "provisional": perf.get("prov", False),
            }
        )
    rows.sort(key=lambda r: r["games"], reverse=True)
    return rows[:4] or None


def fetch_chesscom(username):
    if not username:
        return None
    data = fetch_json(f"https://api.chess.com/pub/player/{username}/stats")
    if not data:
        return None
    rows = []
    for key, label in (("chess_bullet", "Bullet"), ("chess_blitz", "Blitz"), ("chess_rapid", "Rapide"), ("chess_daily", "Journalier")):
        perf = data.get(key)
        if not perf or "last" not in perf:
            continue
        rec = perf.get("record", {})
        games = sum(rec.get(k, 0) for k in ("win", "loss", "draw"))
        rows.append(
            {
                "label": label,
                "rating": perf["last"].get("rating", 0),
                "games": games,
                "prog": 0,
                "provisional": False,
            }
        )
    rows.sort(key=lambda r: r["games"], reverse=True)
    return rows[:4] or None


SEED = json.loads((ROOT / "scripts" / "seed.json").read_text(encoding="utf-8")) if (ROOT / "scripts" / "seed.json").exists() else {}


def fetch_repos(owner, names):
    repos = []
    for name in names:
        data = fetch_json(f"https://api.github.com/repos/{owner}/{name}")
        if not data:
            # repli sur les données figées, pour ne jamais afficher une carte vide
            seed = SEED.get("repos", {}).get(name, {})
            repos.append(
                {
                    "name": name,
                    "desc": seed.get("desc", ""),
                    "lang": seed.get("lang"),
                    "stars": seed.get("stars", 0),
                    "forks": seed.get("forks", 0),
                    "pushed": seed.get("pushed", ""),
                    "url": f"https://github.com/{owner}/{name}",
                }
            )
            continue
        repos.append(
            {
                "name": data.get("name", name),
                "desc": (data.get("description") or "").strip(),
                "lang": data.get("language"),
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "url": data.get("html_url", f"https://github.com/{owner}/{name}"),
                "pushed": (data.get("pushed_at") or "")[:10],
            }
        )
    return repos


# --------------------------------------------------------------------------- #
# Helpers SVG
# --------------------------------------------------------------------------- #

def svg_open(width, height, extra_defs="", extra_css=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" font-family="\'Segoe UI\',Ubuntu,Helvetica,Arial,sans-serif">'
        f"<defs>{extra_defs}</defs>"
        f"<style>{BASE_CSS}{extra_css}</style>"
    )


BASE_CSS = """
@keyframes fadeUp { from { opacity:0; transform:translateY(6px);} to {opacity:1; transform:translateY(0);} }
@keyframes grow { from { transform:scaleX(0);} to {transform:scaleX(1);} }
@keyframes float { 0%,100% { transform:translateY(0);} 50% { transform:translateY(-5px);} }
.fu { animation: fadeUp .7s ease both; }
.bar { transform-origin: left center; animation: grow 1.1s cubic-bezier(.22,1,.36,1) both; }
text { dominant-baseline: middle; }
"""


def card(width, height, t, radius=10):
    return (
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="{radius}" '
        f'fill="{t["bg"]}" stroke="{t["border"]}"/>'
    )


def write(name, content):
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / name).write_text(content, encoding="utf-8")
    print(f"  → assets/{name}")


# --------------------------------------------------------------------------- #
# Widget 1 : bannière
# --------------------------------------------------------------------------- #

def build_header(theme_name):
    t = THEMES[theme_name]
    W, H = 850, 200
    defs = (
        f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{t["accent"]}"/>'
        f'<stop offset="100%" stop-color="{t["accent2"]}"/>'
        f"</linearGradient>"
        f'<pattern id="board" width="40" height="40" patternUnits="userSpaceOnUse">'
        f'<rect width="20" height="20" fill="{t["accent"]}" opacity="0.08"/>'
        f'<rect x="20" y="20" width="20" height="20" fill="{t["accent"]}" opacity="0.08"/>'
        f"</pattern>"
    )
    css = """
    .t1 { font-size: 34px; font-weight: 700; }
    .t2 { font-size: 17px; font-weight: 600; }
    .t3 { font-size: 13px; }
    .pc { font-size: 30px; animation: float 4s ease-in-out infinite; }
    """
    pieces = ["♞", "♜", "♝", "♛", "♟"]
    out = [svg_open(W, H, defs, css)]
    out.append(card(W, H, t, 14))
    out.append(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="13" fill="url(#board)"/>')
    out.append(f'<rect x="0.5" y="0.5" width="6" height="{H-1}" rx="3" fill="url(#g)"/>')

    # pièces flottantes, décoratives
    for i, p in enumerate(pieces):
        x = W - 60 - i * 46
        out.append(
            f'<text class="pc" x="{x}" y="{62 + (i % 2) * 14}" fill="{t["accent"]}" opacity="0.28" '
            f'style="animation-delay:{i * 0.35:.2f}s">{p}</text>'
        )

    name = escape(CONFIG.get("display_name", "Profil"))
    tagline = escape(CONFIG.get("tagline", ""))
    subtitle = escape(CONFIG.get("subtitle", ""))
    out.append(f'<text class="t1 fu" x="38" y="70" fill="{t["text"]}">Salut, moi c\'est {name}. 👋</text>')
    out.append(
        f'<text class="t2 fu" x="38" y="106" fill="{t["accent"]}" style="animation-delay:.15s">{tagline}</text>'
    )
    out.append(
        f'<text class="t3 fu" x="38" y="132" fill="{t["muted"]}" style="animation-delay:.3s">{subtitle}</text>'
    )

    tags = ["Réseaux", "Linux", "Python", "Électronique", "Échecs"]
    x = 38
    for i, tag in enumerate(tags):
        w = 11 + len(tag) * 7.4
        out.append(
            f'<g class="fu" style="animation-delay:{0.45 + i * 0.09:.2f}s">'
            f'<rect x="{x:.0f}" y="152" width="{w:.0f}" height="26" rx="13" fill="{t["panel"]}" stroke="{t["border"]}"/>'
            f'<text x="{x + w / 2:.0f}" y="166" fill="{t["muted"]}" font-size="12" text-anchor="middle">{tag}</text>'
            f"</g>"
        )
        x += w + 9
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------- #
# Widget 2 : échecs
# --------------------------------------------------------------------------- #

def build_chess(theme_name, rows, platform, username):
    t = THEMES[theme_name]
    W = 495
    H = 92 + max(len(rows), 1) * 42
    css = """
    .h { font-size: 15px; font-weight: 600; }
    .l { font-size: 13px; font-weight: 500; }
    .v { font-size: 15px; font-weight: 700; }
    .s { font-size: 11px; }
    """
    out = [svg_open(W, H, "", css)]
    out.append(card(W, H, t))
    out.append(f'<text class="h fu" x="25" y="32" fill="{t["accent"]}">♟ Échecs — {escape(platform)}</text>')
    if username:
        out.append(
            f'<text class="s fu" x="{W - 25}" y="32" fill="{t["muted"]}" text-anchor="end">@{escape(username)}</text>'
        )

    if not rows:
        out.append(
            f'<text class="l fu" x="25" y="70" fill="{t["muted"]}">Compte non configuré — '
            f'renseigne ton pseudo dans widgets.config.json</text>'
        )
        out.append("</svg>")
        return "".join(out)

    # échelle des barres : 800 (débutant) → 2400 (maître)
    lo, hi = 800, 2400
    bar_x, bar_w = 190, 220
    y = 68
    for i, r in enumerate(rows):
        delay = 0.12 * i
        frac = max(0.04, min(1.0, (r["rating"] - lo) / (hi - lo)))
        out.append(
            f'<g class="fu" style="animation-delay:{delay:.2f}s">'
            f'<text class="l" x="25" y="{y}" fill="{t["text"]}">{escape(r["label"])}</text>'
            f'<text class="s" x="25" y="{y + 16}" fill="{t["muted"]}">{r["games"]} parties</text>'
            f'<rect x="{bar_x}" y="{y - 5}" width="{bar_w}" height="10" rx="5" fill="{t["track"]}"/>'
            f'<rect class="bar" x="{bar_x}" y="{y - 5}" width="{bar_w * frac:.1f}" height="10" rx="5" '
            f'fill="{t["accent"]}" style="animation-delay:{delay + 0.2:.2f}s"/>'
            f'<text class="v" x="{W - 25}" y="{y}" fill="{t["text"]}" text-anchor="end">{r["rating"]}'
            f'{"?" if r["provisional"] else ""}</text>'
        )
        if r["prog"]:
            color = t["good"] if r["prog"] > 0 else t["warn"]
            sign = "▲" if r["prog"] > 0 else "▼"
            out.append(
                f'<text class="s" x="{W - 25}" y="{y + 16}" fill="{color}" text-anchor="end">'
                f'{sign} {abs(r["prog"])}</text>'
            )
        out.append("</g>")
        y += 42

    stamp = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    out.append(f'<text class="s" x="25" y="{H - 16}" fill="{t["muted"]}">Mis à jour le {stamp}</text>')
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------- #
# Widget 3 : cartes projets
# --------------------------------------------------------------------------- #

def wrap_text(text, max_chars, max_lines=2):
    words, lines, cur = text.split(), [], ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if not lines:
        return []
    if len(" ".join(lines)) < len(text):
        lines[-1] = lines[-1][: max_chars - 1].rstrip() + "…"
    return lines


def build_repo_card(theme_name, repo):
    t = THEMES[theme_name]
    W, H = 400, 128
    css = """
    .n { font-size: 16px; font-weight: 700; }
    .d { font-size: 12px; }
    .m { font-size: 12px; }
    """
    out = [svg_open(W, H, "", css)]
    out.append(card(W, H, t))
    out.append(f'<text x="24" y="30" font-size="15" fill="{t["muted"]}">📁</text>')
    out.append(f'<text class="n fu" x="46" y="30" fill="{t["accent"]}">{escape(repo["name"])}</text>')

    desc = repo["desc"] or "Pas encore de description."
    for i, line in enumerate(wrap_text(desc, 46)):
        out.append(
            f'<text class="d fu" x="24" y="{58 + i * 18}" fill="{t["muted"]}" '
            f'style="animation-delay:{0.1 + i * 0.05:.2f}s">{escape(line)}</text>'
        )

    x = 24
    if repo.get("lang"):
        color = LANG_COLORS.get(repo["lang"], t["muted"])
        out.append(f'<circle cx="{x + 6}" cy="102" r="6" fill="{color}"/>')
        out.append(f'<text class="m" x="{x + 18}" y="102" fill="{t["text"]}">{escape(repo["lang"])}</text>')
        x += 26 + len(repo["lang"]) * 7
    out.append(f'<text class="m" x="{x}" y="102" fill="{t["muted"]}">★ {repo.get("stars", 0)}</text>')
    x += 40
    if repo.get("forks") is not None:
        out.append(f'<text class="m" x="{x}" y="102" fill="{t["muted"]}">⑂ {repo.get("forks", 0)}</text>')
    if repo.get("pushed"):
        d = repo["pushed"]
        out.append(
            f'<text class="m" x="{W - 24}" y="102" fill="{t["muted"]}" text-anchor="end">'
            f'{d[8:10]}/{d[5:7]}/{d[0:4]}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------- #

def main():
    print("Bannière…")
    for theme in THEMES:
        write(f"header-{theme}.svg", build_header(theme))

    print("Échecs…")
    lichess_user = CONFIG.get("lichess_username", "")
    chesscom_user = CONFIG.get("chesscom_username", "")
    rows = fetch_lichess(lichess_user)
    platform, username = "Lichess", lichess_user
    if not rows:
        rows = fetch_chesscom(chesscom_user)
        if rows:
            platform, username = "Chess.com", chesscom_user
    if not rows:
        print("  ! aucune donnée d'échecs récupérée, widget en mode dégradé", file=sys.stderr)
        platform, username = "Lichess", lichess_user
        rows = []
    for theme in THEMES:
        write(f"chess-{theme}.svg", build_chess(theme, rows, platform, username))

    print("Projets…")
    repos = fetch_repos(CONFIG["github_username"], CONFIG.get("featured_repos", []))
    for repo in repos:
        slug = repo["name"].lower().replace("_", "-")
        for theme in THEMES:
            write(f"repo-{slug}-{theme}.svg", build_repo_card(theme, repo))

    print("Terminé.")


if __name__ == "__main__":
    main()
