"""Builds the profile README and its SVG cards from projects.json.

    py -3 generator/build.py            # fetch live star counts, rebuild everything
    py -3 generator/build.py --offline  # reuse generator/stars.json

Outputs README.md and assets/{hero,sections,cards}/*-{light,dark}.svg.
Text uses subsetted WOFF2 fonts embedded as data URIs (fonts/ are OFL) and emojis are
Noto Emoji PNGs (Apache 2.0, cached in emoji/), so every card renders identically on
every OS with no external requests.
"""
import base64, html, io, json, math, os, random, sys, urllib.request
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = json.load(open(os.path.join(HERE, "projects.json"), encoding="utf-8"))

# ---------------------------------------------------------------- palette
THEMES = {
    "light": dict(bg="#fbf9f4", border="#e4ddcf", ink="#14232a", body="#3b494f", muted="#77838a",
                  lagoon="#0e8a84", star="#b7791f", heroA="#f3eee2", heroB="#fbf9f4"),
    "dark":  dict(bg="#10181d", border="#26333c", ink="#f0f4f2", body="#b6c3c7", muted="#83929a",
                  lagoon="#4fd6c4", star="#f2c14e", heroA="#0b1c24", heroB="#0f171c"),
}
SWATCH = {  # (light, dark)
    "orange": ("#c2410c", "#ff9a5c"), "teal": ("#0f766e", "#4fd6c4"), "green": ("#4d7c0f", "#a8d860"),
    "blue": ("#1d4ed8", "#82aaff"), "rose": ("#be123c", "#ff7d96"), "gold": ("#a16207", "#f2c14e"),
    "indigo": ("#4338ca", "#a5adff"), "cyan": ("#0e7490", "#5fd0e6"),
}
APP_CYCLE = ["orange", "teal", "green", "blue", "rose", "gold", "cyan", "indigo"]

def accent(name, theme): return SWATCH[name][0 if theme == "light" else 1]

# ---------------------------------------------------------------- fonts
def _load(name, wght=None):
    f = TTFont(os.path.join(HERE, "fonts", name), recalcTimestamp=False)
    if wght is not None:
        f = instancer.instantiateVariableFont(f, {"wght": wght})
    buf = io.BytesIO(); f.save(buf)
    return buf.getvalue()

class Font:
    def __init__(self, family, data, fallback):
        self.family, self.data, self.fallback = family, data, fallback
        t = TTFont(io.BytesIO(data))
        self.upm, self.cmap, self.hmtx = t["head"].unitsPerEm, t.getBestCmap(), t["hmtx"].metrics
        self._cache = {}
    def width(self, text, size, spacing=0.0):
        w = sum(self.hmtx[self.cmap[ord(c)]][0] if ord(c) in self.cmap else self.upm * 0.55 for c in text)
        return w * size / self.upm + spacing * len(text)
    def woff2(self, chars):
        key = "".join(sorted(set(chars)))
        if key not in self._cache:
            opts = subset.Options(); opts.flavor = "woff2"; opts.layout_features = ["kern", "liga"]
            t = TTFont(io.BytesIO(self.data), recalcTimestamp=False)
            s = subset.Subsetter(opts); s.populate(text=key + " "); s.subset(t)
            buf = io.BytesIO(); t.flavor = "woff2"; t.save(buf)
            self._cache[key] = base64.b64encode(buf.getvalue()).decode()
        return self._cache[key]

SERIF = Font("ISerif", _load("InstrumentSerif-Regular.ttf"), "Georgia,serif")
ITAL = Font("ISerifI", _load("InstrumentSerif-Italic.ttf"), "Georgia,serif")
SANS = Font("Hanken", _load("HankenGrotesk-VF.ttf", 420), "'Segoe UI',Helvetica,Arial,sans-serif")
MONO = Font("JBMono", _load("JetBrainsMono-VF.ttf", 500), "Consolas,Menlo,monospace")

def wrap(text, font, size, maxw):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if font.width(trial, size) <= maxw or not cur: cur = trial
        else: lines.append(cur); cur = word
    return lines + ([cur] if cur else [])

# ---------------------------------------------------------------- emoji (Noto, cached)
def emoji_data(ch):
    cps = "_".join(f"{ord(c):x}" for c in ch if ord(c) != 0xFE0F)
    path = os.path.join(HERE, "emoji", f"emoji_u{cps}.png")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = f"https://raw.githubusercontent.com/googlefonts/noto-emoji/main/2D/png/128/emoji_u{cps}.png"
        data = urllib.request.urlopen(url).read()
        open(path, "wb").write(data)
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()

def emoji(x, y, size, ch):
    return f'<image x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" href="{emoji_data(ch)}"/>'

# ---------------------------------------------------------------- svg helpers
class Svg:
    def __init__(self, w, h, title, offset=(0, 0)):
        self.w, self.h, self.title, self.offset = w, h, title, offset
        self.parts, self.used, self.css = [], {}, ""
    def text(self, x, y, s, font, size, fill, spacing=0, anchor="start"):
        self.used.setdefault(font, set()).update(s)
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        an = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font.family},{font.fallback}" '
                          f'font-size="{size}" fill="{fill}"{ls}{an}>{html.escape(s, quote=False)}</text>')
    def add(self, raw): self.parts.append(raw)
    def render(self):
        faces = "".join(f"@font-face{{font-family:{f.family};src:url(data:font/woff2;base64,{f.woff2(c)}) format('woff2')}}"
                        for f, c in self.used.items())
        ox, oy = self.offset
        body = "".join(self.parts)
        if ox or oy: body = f'<g transform="translate({ox},{oy})">{body}</g>'
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'role="img" aria-label="{html.escape(self.title)}"><title>{html.escape(self.title)}</title>'
                f'<style>{faces}{self.css}</style>{body}</svg>')

def star_path(cx, cy, r, fill):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5; rr = r if i % 2 == 0 else r * 0.45
        pts.append(f"{cx + rr * math.cos(a):.2f},{cy + rr * math.sin(a):.2f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'

def contours(cx, cy, radii, seed, color, opacity=0.3, width=1.0):
    """Reef/island topography lines: concentric wobbly closed curves."""
    rnd = random.Random(seed)
    harm = [(k, rnd.uniform(0.02, 0.07) / k ** 0.6, rnd.uniform(0, 2 * math.pi)) for k in (2, 3, 4, 5)]
    out = []
    for j, R in enumerate(radii):
        pts = []
        for i in range(96):
            t = 2 * math.pi * i / 96
            r = R * (1 + sum(a * math.sin(k * t + p + j * 0.25) for k, a, p in harm))
            pts.append(f"{cx + r * math.cos(t):.1f},{cy + r * math.sin(t) * 0.82:.1f}")
        op = opacity * (0.45 + 0.55 * (1 - j / max(1, len(radii))))
        out.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-opacity="{op:.2f}"/>')
    return "".join(out)

GITHUB_MARK = ("M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 "
               "1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27"
               "-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 "
               "3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 "
               "1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z")

def domain(url):
    return url.split("//", 1)[-1].split("/", 1)[0].removeprefix("www.")

def link_text(item):
    if item.get("linkText"): return item["linkText"]
    if "marketplace.visualstudio.com" in item["url"]: return "VS Marketplace"
    if "chromewebstore.google.com" in item["url"]: return "Chrome Web Store"
    if "/releases/latest" in item["url"]: return "download"
    if "hacs_repository" in item["url"]: return "install with HACS"
    if domain(item["url"]) == "mayerwin.github.io": return "open in your browser"
    return domain(item["url"])

# ---------------------------------------------------------------- stars
def fetch_stars():
    path = os.path.join(HERE, "stars.json")
    if "--offline" in sys.argv:
        return json.load(open(path))
    stars = {}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    for owner in DATA["profile"]["owners"]:
        req = urllib.request.Request(f"https://api.github.com/users/{owner}/repos?per_page=100&type=owner",
                                     headers={"User-Agent": "profile-readme-builder",
                                              **({"Authorization": f"Bearer {tok}"} if tok else {})})
        for r in json.load(urllib.request.urlopen(req)):
            if not r["private"]: stars[r["full_name"].lower()] = r["stargazers_count"]
    json.dump(stars, open(path, "w"), indent=1, sort_keys=True)
    return stars

STARS = fetch_stars()
def stars_of(repo): return STARS.get((repo or "").lower(), 0)
SHOW_STARS = 3   # hide counts below this

# ---------------------------------------------------------------- layout
# A grid "unit" is: card image (CARD_W) + space + GitHub button (BTN). Two units and a
# space fit GitHub's narrowest desktop README column (807 px); on phones the button
# wraps under its card.
CARD_W, BTN, INSET = 358, 36, 4
DRAWN = CARD_W - INSET           # card drawn from x=INSET to the right edge
PAD = 22

def card_layout(item, style):
    if style == "app":
        lines = wrap(item["desc"], SANS, 14.5, DRAWN - 2 * PAD)
        if len(lines) > 3: print("  ! desc over 3 lines:", item["name"])
        lines = lines[:3]
        return lines, 108 + 20.5 * (len(lines) - 1) + 36 + 22
    lines = wrap(item["desc"], SANS, 13.8, DRAWN - 2 * PAD)
    if len(lines) > 3: print("  ! desc over 3 lines:", item["name"])
    lines = lines[:3]
    foot = 30 if item.get("url") else 0
    return lines, 96 + 19 * (len(lines) - 1) + foot + 22

def card(theme, item, style, acc, H, seed):
    p = THEMES[theme]; lines, _ = card_layout(item, style)
    s = Svg(CARD_W, H + 2 * INSET, f"{item['name']}: {item['desc']}", offset=(INSET, INSET))
    W = DRAWN
    s.add(f'<clipPath id="c"><rect width="{W}" height="{H}" rx="16"/></clipPath>')
    s.add(f'<rect width="{W}" height="{H}" rx="16" fill="{p["bg"]}"/>')
    big = style == "app"
    s.add('<g clip-path="url(#c)">' + contours(W - 8, 4, [22 + 17 * i for i in range(7 if big else 5)], seed, acc,
                                                 0.34 if big else 0.26) +
          f'<rect width="{W}" height="3" fill="{acc}"/></g>')
    s.add(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="15.5" fill="none" stroke="{p["border"]}"/>')
    es = 24 if big else 21
    ly = 38 if big else 34
    s.add(emoji(PAD, ly - es + 5, es, item["emoji"]))
    s.text(PAD + es + 9, ly, item["label"], MONO, 11, p["muted"], spacing=1.3)
    n = stars_of(item.get("repo"))
    if n >= SHOW_STARS:
        s.text(W - PAD, ly, str(n), MONO, 12, p["star"], anchor="end")
        s.add(star_path(W - PAD - MONO.width(str(n), 12) - 9, ly - 4.3, 5.5, p["star"]))
    if big:
        s.text(PAD, 80, item["name"], SERIF, 31, p["ink"])
        y = 108
        for line in lines: s.text(PAD, y, line, SANS, 14.5, p["body"]); y += 20.5
    else:
        s.text(PAD, 70, item["name"], SERIF, 27, p["ink"])
        y = 96
        for line in lines: s.text(PAD, y, line, SANS, 13.8, p["body"]); y += 19
    if item.get("url"):
        s.text(PAD, H - 21, f"↗ {link_text(item)}", MONO, 12, acc, spacing=0.4)
    return s.render()

def gh_button(theme, title):
    p = THEMES[theme]
    s = Svg(BTN, BTN + INSET, title)
    s.add(f'<rect x=".5" y=".5" width="{BTN-1}" height="{BTN-1}" rx="10" fill="{p["bg"]}" stroke="{p["border"]}"/>')
    s.add(f'<path transform="translate(8.5,8.5) scale(1.19)" d="{GITHUB_MARK}" fill="{p["ink"]}"/>')
    return s.render()

def blank(): return f'<svg xmlns="http://www.w3.org/2000/svg" width="{BTN}" height="{BTN + INSET}"/>'

# ---------------------------------------------------------------- hero + sections
def hero(theme, stars, projects):
    p = THEMES[theme]; W, H = 846, 250
    s = Svg(W, H, f"{DATA['profile']['first']} {DATA['profile']['last']}")
    s.css = ("@keyframes drift{from{transform:translate(0,0) rotate(0deg)}to{transform:translate(-18px,8px) rotate(-3deg)}}"
             ".reef{transform-origin:690px 125px;animation:drift 14s ease-in-out infinite alternate}"
             "@media (prefers-reduced-motion:reduce){.reef{animation:none}}")
    s.add(f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p["heroA"]}"/>'
          f'<stop offset="1" stop-color="{p["heroB"]}"/></linearGradient>'
          f'<clipPath id="c"><rect width="{W}" height="{H}" rx="18"/></clipPath></defs>')
    s.add(f'<rect width="{W}" height="{H}" rx="18" fill="url(#g)"/>')
    s.add(f'<g clip-path="url(#c)"><g class="reef">'
          + contours(700, 130, [34 + 26 * i for i in range(11)], 7, p["lagoon"], 0.42, 1.2)
          + f'<circle cx="700" cy="130" r="5" fill="{p["lagoon"]}"/></g></g>')
    s.add(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="17.5" fill="none" stroke="{p["border"]}"/>')
    x = 44; pr = DATA["profile"]
    s.add(emoji(x, 38, 30, pr["kickerEmoji"]))
    s.text(x + 42, 62, pr["kicker"], MONO, 21, p["lagoon"], spacing=2.6)
    s.text(x, 158, pr["first"], SERIF, 104, p["ink"], spacing=-1)
    s.text(x + SERIF.width(pr["first"], 104, -1) + 26, 158, pr["last"], ITAL, 104, p["lagoon"], spacing=-1)
    s.add(star_path(x + 12, 207, 12, p["star"]))
    s.text(x + 34, 214, f"{stars} STARS  ·  {projects} PROJECTS", MONO, 21, p["muted"], spacing=1.8)
    return s.render()

def section(theme, cat, acc):
    p = THEMES[theme]; W, H = 846, 92
    n = len(cat["items"]); note = f"{n} PROJECT{'S' if n > 1 else ''}"
    s = Svg(W, H, f"{cat['emoji']} {cat['title']}")
    nw = MONO.width(note, 20, 2.2)
    size = 50
    while SERIF.width(cat["title"], size) > W - 66 - nw - 30: size -= 2
    s.add(emoji(0, 22, 46, cat["emoji"]))
    s.text(62, 64, cat["title"], SERIF, size, p["ink"])
    s.text(W, 62, note, MONO, 20, p["muted"], spacing=2.2, anchor="end")
    s.add(f'<rect x="0" y="82" width="{W}" height="1.5" fill="{p["border"]}"/>')
    s.add(f'<rect x="0" y="80.5" width="84" height="4" fill="{acc}"/>')
    return s.render()

# ---------------------------------------------------------------- write
WRITTEN = set()
def put(rel, svg):
    WRITTEN.add(rel)
    path = os.path.join(ROOT, rel); os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="\n").write(svg)

def picture(base, alt, width=None, href=None, themed=True):
    w = f' width="{width}"' if width else ""
    if themed:
        img = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{base}-dark.svg">'
               f'<img src="{base}-light.svg"{w} alt="{html.escape(alt)}"></picture>')
    else:
        img = f'<img src="{base}.svg"{w} alt="{html.escape(alt)}">'
    return f'<a href="{href}">{img}</a>' if href else img

def main():
    pr, cats = DATA["profile"], DATA["categories"]
    items = [i for c in cats for i in c["items"]]
    repos = {i["repo"].lower() for i in items if i.get("repo")}
    total = sum(stars_of(r) for r in repos)

    plan = []   # heights are uniform within a category so rows line up
    for c in cats:
        H = max(card_layout(i, c["style"])[1] for i in c["items"])
        for k, it in enumerate(c["items"]):
            acc_name = APP_CYCLE[k % len(APP_CYCLE)] if c["style"] == "app" else c["accent"]
            plan.append((it, c["style"], acc_name, H, k * 31 + len(c["slug"])))

    for t in THEMES:
        put(f"assets/hero/hero-{t}.svg", hero(t, total, len(items)))
        put(f"assets/cards/_github-{t}.svg", gh_button(t, "Source on GitHub"))
        for c in cats:
            put(f"assets/sections/{c['slug']}-{t}.svg", section(t, c, accent(c["accent"], t)))
        for it, style, acc_name, H, seed in plan:
            put(f"assets/cards/{it['slug']}-{t}.svg", card(t, it, style, accent(acc_name, t), H, seed))
    put("assets/cards/_blank.svg", blank())
    # drop cards and section banners of projects or categories no longer listed
    for sub in ("cards", "sections"):
        folder = os.path.join(ROOT, "assets", sub)
        for f in os.listdir(folder):
            if os.path.join("assets", sub, f).replace(os.sep, "/") not in WRITTEN:
                os.remove(os.path.join(folder, f)); print("  - removed stale", sub + "/" + f)

    L = [f'<p align="center">{picture("assets/hero/hero", pr["first"] + " " + pr["last"], href=pr["website"])}</p>\n',
         f'<p align="center">{html.escape(pr["tagline"])}<br>\n'
         f'🌐 <a href="{pr["website"]}"><b>{domain(pr["website"])}</b></a></p>\n']
    for c in cats:
        L.append(f'<p align="center">{picture("assets/sections/" + c["slug"], c["emoji"] + " " + c["title"])}</p>\n')
        units = []
        for it in c["items"]:
            repo_url = f"https://github.com/{it['repo']}" if it.get("repo") else None
            n = stars_of(it.get("repo"))
            alt = f"{it['name']}{f' ({n} stars)' if n >= SHOW_STARS else ''}: {it['desc']}"
            cardp = picture(f"assets/cards/{it['slug']}", alt, CARD_W, it.get("url") or repo_url)
            btn = (picture("assets/cards/_github", f"{it['name']} source on GitHub", BTN, repo_url) if repo_url
                   else picture("assets/cards/_blank", "", BTN, themed=False))
            units.append(f"{cardp}\n{btn}")
        L.append('<p align="center">\n' + "\n".join(units) + "\n</p>\n")
    # the same content as real text (collapsed): searchable, indexable, readable by screen readers and LLMs
    T = ['<details>\n<summary>📋 <b>All projects as text</b></summary>\n']
    for c in cats:
        T.append(f"\n### {c['emoji']} {c['title']}\n")
        for it in c["items"]:
            links = []
            if it.get("url"): links.append(f"[{link_text(it)}]({it['url']})")
            if it.get("repo"): links.append(f"[source](https://github.com/{it['repo']})")
            n = stars_of(it.get("repo"))
            star = f" ⭐ {n}" if n >= SHOW_STARS else ""
            T.append(f"- **{it['name']}**{star}: {it['desc']} {' · '.join(links)}")
    T.append("\n</details>\n")
    L.append("\n".join(T))
    open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print(f"built: {total} stars, {len(items)} projects")

main()
