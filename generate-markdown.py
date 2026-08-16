#!/usr/bin/env python3
"""Render case-study.md for every project from its content.json.
Run from the package root:  python3 generate-markdown.py
Edit content.json, re-run this, and the markdown stays in sync."""
import json, pathlib, sys

root = pathlib.Path(__file__).parent
out = []

for d in sorted((root / "projects").iterdir()):
    cj = d / "content.json"
    if not cj.exists():
        continue
    c = json.loads(cj.read_text())
    L = []
    L.append(f"# {c['title']}")
    L.append("")
    L.append(f"**{c['tagline']}**")
    L.append("")
    L.append(c["summary"])
    L.append("")
    facts = [("Role", c.get("role")), ("Client", c.get("client")),
             ("Year", c.get("year")), ("Duration", c.get("duration")),
             ("Team", c.get("team")), ("Status", c.get("status")),
             ("Platforms", ", ".join(c.get("platforms", []))),
             ("Tools", ", ".join(c.get("tools", [])))]
    L.append("| | |")
    L.append("|---|---|")
    for k, v in facts:
        if v:
            L.append(f"| **{k}** | {v} |")
    L.append("")
    if c.get("metrics"):
        L.append("## At a glance")
        L.append("")
        for m in c["metrics"]:
            L.append(f"- **{m['value']}** — {m['label']}")
        L.append("")
    if c.get("links"):
        L.append("## Links")
        L.append("")
        for l in c["links"]:
            L.append(f"- [{l['label']}]({l['url']})")
        L.append("")
    for s in c.get("sections", []):
        L.append(f"## {s['heading']}")
        L.append("")
        L.append(s["body"])
        L.append("")
        for img in s.get("images", []):
            L.append(f"![{img['alt']}]({img['src']})")
            if img.get("caption"):
                L.append("")
                L.append(f"*{img['caption']}*")
            L.append("")
    if c.get("todo"):
        L.append("---")
        L.append("")
        L.append("## TODO — needs Abdallah")
        L.append("")
        L.append("_Not published copy. These are gaps I could not fill from the Figma file or the Notion export._")
        L.append("")
        for t in c["todo"]:
            L.append(f"- [ ] {t}")
        L.append("")
    (d / "case-study.md").write_text("\n".join(L))
    missing = []
    for s in c.get("sections", []):
        for img in s.get("images", []):
            if not (d / img["src"]).exists():
                missing.append(img["src"])
    if c.get("cover") and not (d / c["cover"]).exists():
        missing.append(c["cover"] + " (cover)")
    out.append((c["order"], c["title"], d.name, len(c.get("sections", [])),
                len(c.get("todo", [])), missing))

print(f"{'#':<3}{'project':<14}{'sections':>9}{'todos':>7}  missing assets")
for o, t, n, ns, nt, miss in sorted(out):
    print(f"{o:<3}{t:<14}{ns:>9}{nt:>7}  {', '.join(miss) if miss else '-'}")
