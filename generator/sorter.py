"""Drag-and-drop board for regrouping the profile projects.

  py -3 generator/sorter.py build [out.html]   # board page from projects.json (default generator/sorter.html)
  py -3 generator/sorter.py apply layout.json  # write a finished board layout back into projects.json

The board shows the live layout; dragging, renaming, adding sections and hiding
projects saves a layout document {base, categories, notes, done}. `apply` takes
that document (or just its "data" part) and rewrites projects.json: section order,
titles, emojis, item order, new sections and the hidden list. See README.md.
"""
import hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS = os.path.join(HERE, "projects.json")
SWATCHES = ["orange", "teal", "green", "blue", "rose", "gold", "cyan", "indigo"]

def load(): return json.load(open(PROJECTS, encoding="utf-8"))

def save(d):
    open(PROJECTS, "w", encoding="utf-8", newline="\n").write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")

def board_layout(d):
    cats = [{"id": c["slug"], "emoji": c["emoji"], "title": c["title"], "items": [i["slug"] for i in c["items"]]}
            for c in d["categories"]]
    cats.append({"id": "hidden", "emoji": "🙈", "title": "Hide from README", "hidden": True,
                 "items": [i["slug"] for i in d.get("hidden", [])]})
    return cats

def build(out):
    d = load()
    cat = {}
    for c in d["categories"]:
        for i in c["items"]:
            cat[i["slug"]] = [i["emoji"], i["name"], i["label"], i["desc"], c["slug"], c["title"]]
    for i in d.get("hidden", []):
        cat[i["slug"]] = [i["emoji"], i["name"], i["label"], i["desc"], "hidden", "Hidden"]
    layout = board_layout(d)
    base = hashlib.sha1(json.dumps(layout, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    page = open(os.path.join(HERE, "sorter.template.html"), encoding="utf-8").read()
    page = (page.replace("/*CATALOG*/{}", json.dumps(cat, ensure_ascii=False))
                .replace("/*LAYOUT*/[]", json.dumps(layout, ensure_ascii=False))
                .replace("/*BASE*/", base))
    open(out, "w", encoding="utf-8", newline="\n").write(page)
    print(f"board written to {out} (base {base}, {len(cat)} projects)")

def slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section"

def apply(path):
    doc = json.load(open(path, encoding="utf-8"))
    doc = doc.get("data", doc)
    d = load()
    items = {i["slug"]: i for c in d["categories"] for i in c["items"]}
    items.update({i["slug"]: i for i in d.get("hidden", [])})
    old = {c["slug"]: c for c in d["categories"]}
    placed = [s for c in doc["categories"] for s in c["items"]]
    missing, unknown = set(items) - set(placed), set(placed) - set(items)
    if missing or unknown or len(placed) != len(set(placed)):
        sys.exit(f"layout does not match projects.json: missing {sorted(missing)}, unknown {sorted(unknown)}")
    cats, hidden, used = [], [], {c.get("accent") for c in d["categories"]}
    for c in doc["categories"]:
        if c.get("hidden"):
            hidden = [items[s] for s in c["items"]]; continue
        if not c["items"]: continue
        prev = old.get(c["id"])
        slug = c["id"] if prev else slugify(c["title"])
        accent = prev["accent"] if prev else next((s for s in SWATCHES if s not in used), SWATCHES[len(cats) % 8])
        used.add(accent)
        cats.append({"slug": slug, "title": c["title"].strip(), "emoji": c["emoji"].strip(),
                     "style": prev["style"] if prev else "tool", "accent": accent,
                     "items": [items[s] for s in c["items"]]})
        if not prev: print(f"  new section '{c['title']}': style tool, accent {accent} (edit projects.json to change)")
    d["categories"] = cats
    if hidden: d["hidden"] = hidden
    else: d.pop("hidden", None)
    save(d)
    if doc.get("notes"): print("notes on the board:", doc["notes"])
    print(f"projects.json updated: {len(cats)} sections, {len(placed) - len(hidden)} shown, {len(hidden)} hidden")

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        build(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "sorter.html"))
    elif len(sys.argv) == 3 and sys.argv[1] == "apply":
        apply(sys.argv[2])
    else:
        sys.exit(__doc__)
