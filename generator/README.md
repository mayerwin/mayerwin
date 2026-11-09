# Profile README generator

`README.md` and everything under `assets/` are generated. Edit `projects.json`, then:

```
py -3 generator/build.py            # fetches live star counts (set GITHUB_TOKEN to avoid rate limits)
py -3 generator/build.py --offline  # reuses stars.json
```

The line above the name is `profile.kicker` with `kickerEmoji` ("Ia ora na" is "hello" in Tahitian). `kickerAlternatives` keeps other lines Erwin liked, ready to swap in; the build ignores it.

Needs `fonttools` and `brotli` (`py -3 -m pip install fonttools brotli`).

- `categories`: one section each, cards in the order given. `"style": "app"` gives the large card, `"tool"` the compact one. `"accent"` is the section colour (a `SWATCH` name in `build.py`; app cards cycle through colours instead). Cards and banners of slugs no longer listed are removed on build. Card heights are uniform within a section; the build warns when a description runs over 3 lines.
- Each item: `emoji` (icon), `label` (small caps line), `desc`, optional `url` (the card links there) and `repo` (the GitHub button links there; the card too when there is no `url`). `linkText` overrides the footer link label.
- Every image carries alt text (name, stars, description), and the page ends with a collapsed "All projects as text" list with real links, so search engines, screen readers and LLMs see everything the cards show.
- Star counts show from 3 stars up. The header total is the sum over the repos listed.
- `.github/workflows/refresh.yml` rebuilds daily and folds any change into the single commit (this repo keeps no history).

Each card has a light and a dark SVG, picked by GitHub's theme through `<picture>`. Text is set in Instrument Serif, Hanken Grotesk and JetBrains Mono (SIL Open Font License, `fonts/`), subsetted and embedded; emojis are Noto Emoji PNGs (Apache 2.0, cached in `emoji/`). Cards therefore render identically on every OS.

Layout: each card (358 px) is followed by a space and a 36 px GitHub button, so two cards per row fit GitHub's narrowest desktop column (807 px). On phones each card takes the full width and its button wraps underneath.

## Sorting board (regroup projects by drag and drop)

For reorganising sections, it is easier to drag cards around than to edit `projects.json` by hand.

1. `py -3 generator/sorter.py build` writes `generator/sorter.html` (git-ignored) from the current `projects.json`: one panel per section, plus a "Hide from README" panel for projects kept in `projects.json` under `hidden` but not shown. Tags mark projects that sit somewhere else than on the live page.
2. Publish it as a private Claude artifact with the `db` and `user` capabilities, reusing the existing board so the link stays the same: https://claude.ai/artifact/45oP2z2cZJzLR91wB6bUga (read it first in a new session, then publish with that URL). The page also works opened locally, saving to the browser only.
3. Erwin drags projects and sections, renames them (title and emoji), adds or deletes sections, hides projects, writes notes, and presses Done. Every change is saved in the artifact's database, document `board/layout` (`{base, categories, notes, done}`). `base` identifies the `projects.json` the board was built from; a saved layout from an older build is ignored, so a rebuilt board always opens on the live layout.
4. Read that document, save it as JSON, and run `py -3 generator/sorter.py apply layout.json`. It rewrites section order, titles, emojis, item order, new sections (compact `tool` style and an unused accent by default) and the `hidden` list, then prints the board notes. Then `build.py`, check, and fold into the single commit.
