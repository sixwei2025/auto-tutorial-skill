#!/usr/bin/env python3
"""Build a single-file interactive steps guide from steps.json / guide-steps.json.

Lightweight HTML: TOC + prev/next + do/see + real screenshots.
Does not fabricate UI; missing shot paths are listed as blockers in the page.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import sys
from pathlib import Path


def _load_steps(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "steps" not in data:
        raise SystemExit(f"invalid steps file: {path}")
    return data


def _data_uri(root: Path, rel: str | None) -> tuple[str | None, str | None]:
    if not rel:
        return None, "missing path"
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        return None, f"path escapes root: {rel}"
    if not p.is_file():
        return None, f"file not found: {rel}"
    mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    if not mime.startswith("image/"):
        return None, f"not an image: {rel}"
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}", None


def _shot_block(root: Path, label: str, rel: str | None) -> str:
    uri, err = _data_uri(root, rel)
    safe_label = html.escape(label)
    safe_rel = html.escape(rel or "")
    if uri:
        return (
            f'<figure class="shot"><figcaption>{safe_label}'
            f'<span class="path">{safe_rel}</span></figcaption>'
            f'<img src="{uri}" alt="{safe_label}" loading="lazy"/></figure>'
        )
    return (
        f'<figure class="shot missing"><figcaption>{safe_label}'
        f'<span class="path">{safe_rel or "—"}</span></figcaption>'
        f'<p class="block">缺图阻塞：{html.escape(err or "unknown")}</p></figure>'
    )


def build_html(root: Path, data: dict) -> str:
    topic = html.escape(str(data.get("topic") or "操作指南"))
    goal = html.escape(str(data.get("goal") or ""))
    audience = html.escape(str(data.get("audience") or ""))
    review = data.get("review") or {}
    status = html.escape(str(review.get("status") or "draft"))
    steps = list(data.get("steps") or [])
    n = len(steps)

    toc_items = []
    panels = []
    blockers = []

    for i, step in enumerate(steps):
        sid = str(step.get("id") or f"s{i+1:02d}")
        goal_s = str(step.get("goal") or "")
        do = str(step.get("do") or "")
        see = str(step.get("see") or "")
        who = str(step.get("who") or "")
        note = str(step.get("note") or "")
        note_kind = str(step.get("note_kind") or "")
        evidence = str(step.get("evidence") or "")
        action = str(step.get("action_level") or "")
        shots = step.get("shots") or {}
        before = shots.get("before")
        after = shots.get("after")
        extras = shots.get("extra") or []

        for key, rel in (("before", before), ("after", after)):
            if not rel or not (root / rel).is_file():
                blockers.append(f"{sid}:{key}->{rel}")
        for j, rel in enumerate(extras):
            if rel and not (root / rel).is_file():
                blockers.append(f"{sid}:extra[{j}]->{rel}")
        if not evidence.strip():
            blockers.append(f"{sid}:evidence")

        toc_items.append(
            f'<li><a href="#step-{html.escape(sid)}" data-goto="{i}">'
            f'{i+1}. {html.escape(goal_s or sid)}</a></li>'
        )

        who_html = (
            f'<p class="who"><strong>Who</strong> {html.escape(who)}</p>' if who else ""
        )
        note_html = ""
        if note:
            kind = html.escape(note_kind or "note")
            note_html = (
                f'<p class="note {kind}"><strong>{kind}</strong> '
                f"{html.escape(note)}</p>"
            )
        action_html = (
            f'<p class="meta">action_level: {html.escape(action)}</p>' if action else ""
        )
        evidence_html = (
            f'<p class="evidence"><strong>Evidence</strong> '
            f"{html.escape(evidence)}</p>"
            if evidence
            else '<p class="evidence block">Evidence 缺失（阻塞）</p>'
        )

        extras_html = "".join(
            _shot_block(root, f"extra[{j}]", rel) for j, rel in enumerate(extras)
        )

        prev_disabled = "disabled" if i == 0 else ""
        next_disabled = "disabled" if i >= n - 1 else ""
        panels.append(
            f"""
<section class="step" id="step-{html.escape(sid)}" data-index="{i}" hidden>
  <header>
    <p class="progress">步骤 {i+1} / {n}</p>
    <h2>{html.escape(goal_s or sid)}</h2>
    <p class="id">id: {html.escape(sid)}</p>
  </header>
  <div class="card do"><h3>Do</h3><p>{html.escape(do)}</p></div>
  <div class="card see"><h3>See</h3><p>{html.escape(see)}</p></div>
  {who_html}{note_html}{action_html}{evidence_html}
  <div class="shots">
    {_shot_block(root, "before", before)}
    {_shot_block(root, "after", after)}
    {extras_html}
  </div>
  <nav class="nav">
    <button type="button" data-nav="prev" {prev_disabled}>上一步</button>
    <button type="button" data-nav="next" {next_disabled}>下一步</button>
  </nav>
</section>
"""
        )

    block_banner = ""
    if blockers:
        items = "".join(f"<li>{html.escape(b)}</li>" for b in blockers)
        block_banner = (
            f'<div class="banner block"><strong>缺图/缺证据阻塞</strong>'
            f"<ul>{items}</ul>"
            f"<p>补齐真实截图前勿定稿旁白或正式渲染视频。</p></div>"
        )

    toc = "\n".join(toc_items)
    body = "\n".join(panels)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{topic} · 操作指南</title>
<style>
:root {{
  --bg:#0f1115; --card:#1a1f29; --text:#e8ecf1; --muted:#9aa3b2;
  --accent:#ff4d4f; --ok:#3ddc97; --line:#2a3344;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; font:16px/1.55 system-ui,-apple-system,sans-serif;
  background:var(--bg); color:var(--text);
}}
.layout {{ display:grid; grid-template-columns:260px 1fr; min-height:100vh; }}
aside {{
  border-right:1px solid var(--line); padding:1.25rem; background:#12161e;
  position:sticky; top:0; height:100vh; overflow:auto;
}}
aside h1 {{ font-size:1.05rem; margin:0 0 .5rem; }}
aside .meta, .id, .progress {{ color:var(--muted); font-size:.85rem; }}
aside ol {{ padding-left:1.1rem; }}
aside a {{ color:#9ecbff; text-decoration:none; }}
aside a:hover, aside a.active {{ color:#fff; }}
main {{ padding:1.5rem; max-width:980px; }}
.banner.block {{
  background:#3a1515; border:1px solid #a33; padding:1rem; border-radius:10px;
  margin-bottom:1rem;
}}
.card {{
  background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:1rem 1.1rem; margin:.75rem 0;
}}
.card h3 {{ margin:0 0 .35rem; color:var(--accent); font-size:.95rem; }}
.shots {{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:1rem; margin:1rem 0;
}}
figure.shot {{
  margin:0; background:var(--card); border:1px solid var(--line);
  border-radius:12px; overflow:hidden;
}}
figure.shot img {{ display:block; width:100%; height:auto; background:#000; }}
figcaption {{
  padding:.55rem .75rem; font-size:.85rem; color:var(--muted);
  display:flex; justify-content:space-between; gap:.5rem; flex-wrap:wrap;
}}
figcaption .path {{ opacity:.75; word-break:break-all; }}
.shot.missing .block, p.block {{ color:#ffb4b4; }}
.nav {{ display:flex; gap:.75rem; margin-top:1rem; }}
button {{
  background:var(--accent); color:#fff; border:0; border-radius:999px;
  padding:.55rem 1.1rem; font-weight:600; cursor:pointer;
}}
button[disabled] {{ opacity:.35; cursor:not-allowed; }}
.note.warning {{ color:#ffcc66; }}
.note.limit {{ color:#ffb4b4; }}
.evidence {{ color:var(--muted); font-size:.9rem; }}
@media (max-width:860px) {{
  .layout {{ grid-template-columns:1fr; }}
  aside {{ position:relative; height:auto; }}
}}
</style>
</head>
<body>
<div class="layout">
  <aside>
    <h1>{topic}</h1>
    <p class="meta">audience: {audience or "—"}</p>
    <p class="meta">goal: {goal or "—"}</p>
    <p class="meta">review: {status}</p>
    <h2 style="font-size:.95rem;margin:1rem 0 .4rem">目录</h2>
    <ol id="toc">{toc or "<li>（无步骤）</li>"}</ol>
  </aside>
  <main>
    {block_banner}
    {body or "<p>无步骤</p>"}
  </main>
</div>
<script>
(function(){{
  const steps=[...document.querySelectorAll("section.step")];
  const links=[...document.querySelectorAll("#toc a")];
  function show(i){{
    if(!steps.length) return;
    i=Math.max(0, Math.min(steps.length-1, i));
    steps.forEach((el,idx)=>{{ el.hidden = idx!==i; }});
    links.forEach((a,idx)=>{{ a.classList.toggle("active", idx===i); }});
    const cur=steps[i];
    history.replaceState(null,"","#"+cur.id);
  }}
  links.forEach(a=>a.addEventListener("click",e=>{{
    e.preventDefault(); show(Number(a.dataset.goto||0));
  }}));
  document.querySelectorAll("button[data-nav]").forEach(btn=>{{
    btn.addEventListener("click",()=>{{
      const sec=btn.closest("section.step");
      const i=Number(sec.dataset.index||0);
      show(btn.dataset.nav==="next"? i+1 : i-1);
    }});
  }});
  const hash=location.hash.replace(/^#/,"");
  const start=Math.max(0, steps.findIndex(s=>s.id===hash));
  show(start===-1?0:start);
}})();
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build single-file steps HTML guide")
    ap.add_argument("root", type=Path, help="project ROOT containing steps.json")
    ap.add_argument(
        "--steps",
        default="",
        help="steps file path relative to ROOT (default: steps.json or guide-steps.json)",
    )
    ap.add_argument(
        "--out",
        default="guide.html",
        help="output HTML path relative to ROOT (default: guide.html)",
    )
    ap.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="exit 2 if any core before/after/evidence is missing",
    )
    args = ap.parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"ROOT not found: {root}")

    if args.steps:
        steps_path = (root / args.steps).resolve()
    else:
        for name in ("steps.json", "guide-steps.json"):
            cand = root / name
            if cand.is_file():
                steps_path = cand
                break
        else:
            raise SystemExit("steps.json / guide-steps.json not found in ROOT")

    data = _load_steps(steps_path)
    html_text = build_html(root, data)
    out = (root / args.out).resolve()
    out.write_text(html_text, encoding="utf-8")
    print(f"wrote {out}")

    # recompute blockers for exit code
    blockers = []
    for s in data.get("steps") or []:
        sid = s.get("id")
        shots = s.get("shots") or {}
        for k in ("before", "after"):
            rel = shots.get(k)
            if not rel or not (root / rel).is_file():
                blockers.append(f"{sid}:{k}")
        if not str(s.get("evidence") or "").strip():
            blockers.append(f"{sid}:evidence")
    if blockers:
        print("BLOCKERS:")
        print("\n".join(blockers))
        if args.fail_on_missing:
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
