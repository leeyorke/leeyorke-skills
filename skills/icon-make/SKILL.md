---
name: icon-make
description: Generate app icons and logos from a reference image — reverse-engineer its design DNA (colors, stroke weight, slant, terminal style) via pixel analysis, rebuild it as a parametric SVG, and emit verified multi-size PNGs plus a Windows .ico. Use when creating or redesigning an app icon/logo, converting a reference image into an icon, or when the user mentions icon/logo/favicon/.ico design or iteration.
metadata:
   version: 0.0.1
---

# Icon Make

Reverse-engineer a reference image into a parametric SVG, then rasterize verified multi-size PNGs + a Windows `.ico`; iterate with the user until the letterform is right.

## Quick start

```bash
# 0. isolated tooling dir FIRST (NEVER skip — Traps #1); scripts resolve resvg from cwd
mkdir icon-work && cd icon-work && npm init -y && npm install @resvg/resvg-js
cp -r <skillDir>/scripts .

# 1. analyze the reference
node scripts/analyze-image.mjs ../reference.png

# 2. build + render (s-builder.mjs is a worked example; adapt its technique)
node scripts/s-builder.mjs out --w 175 --rot 8 --corner 229

# 3. verify with icon-lib.mjs helpers (pixel diff / transparency / ICO entries)
```

## Workflow

### 1. Set up isolated tooling FIRST
Working dir with its **own** `package.json` (never skip this), then `npm install @resvg/resvg-js`;
scripts resolve resvg from **cwd** — run them there. If a tooling dir with resvg already exists
on this machine (ask the user), reuse it; a fresh install is cheap (~15s, npm-cached) regardless.

### 2. Reverse-engineer the reference
`analyze-image.mjs` reports bg/ink colors, bbox, margins, per-row/column extents, ASCII preview.
Derive the **design DNA** yourself: exact colors (sample, don't guess); stroke weight (extents
where the glyph is a plain stroke — not at curves); slant angle (fit an edge's extents; **verify
direction against the image**); terminal style (flat cut / rounded hook / pointed wedge); letter
box + margins for the optical size.

### 3. Build the SVG parametrically
Two proven constructions (math in REFERENCE.md):
- **Stroked centerline**: letter as 1–2 SVG arc commands + `stroke-width`, butt caps.
- **Offset polygon** (for tapered/pointed terminals): sample the centerline, offset
  ±w/2 along sampled normals, shrink width to 0 over the tail's last N px.
  `s-builder.mjs` is a complete worked example.
Parametrize everything (weight, radii, box, terminal angles, taper, rotation, corner radius,
colors) so each review round is a parameter change, not a redraw. Corners: `rx` on the background
rect; outside stays transparent (alpha 0).

### 4. Variant matrix + review loop
Render 3–5 **meaningfully different** variants into one labeled contact sheet, show
it, and let the user pick a direction via `ask_user_question` (slant? corner size?
terminal style?). Then fine-tune parameters. Don't dump 10 near-identical variants;
don't fine-tune before the big decisions are made.

### 5. Final assets + verification
Emit: `icon.svg` (RDP-simplified outline, eps ≈ 0.4px), `icon-1024.png` master, size
set 16/24/32/48/64/128/256/512/1024, and `icon.ico` (≤256 sizes, PNG payloads).
Verify before presenting:
- `diffPng` new construction vs a stroked reference — expect only a thin AA band (~0.2%); more means a real bug (Traps #7)
- `coverageAt`/`topInkRow` edge probes at 50% threshold on both renders (±1px)
- corner alpha = 0; bg/ink RGB exact at sampled pixels
- `verifyIco` — every entry's declared size must equal its PNG payload size
- small-size strip (256→16px); ultra-bold glyphs lose counters below ~32px — OK, note it

### 6. Install (only after user approval)
Stage outside the target, get explicit approval, then copy (e.g. `build/icon.png`,
`build/icon.ico`, `build/icon.svg`), hash-verify, clean up one-off scripts (keep the
generator + SVG source). Tell the user what needs a rebuild vs what picks up on next start.

## Scripts

| File | Purpose |
|---|---|
| `scripts/icon-lib.mjs` | PNG decode/encode, resvg render, ICO pack/verify, pixel diff, coverage probe, RDP |
| `scripts/analyze-image.mjs` | reference image → colors / bbox / extents / ASCII preview |
| `scripts/s-builder.mjs` | worked example: parametrized bold geometric S (offset polygon + tapered tail) |

## Traps (all learned the hard way — details in REFERENCE.md)

1. **npm walks up**: `npm install` in a dir with NO package.json pollutes the parent
   project (adds deps to its package.json, mangles its node_modules). Always
   `npm init -y` first; keep tooling outside the repo or gitignored.
2. **resvg `fitTo.width`**: pass the SVG's own width — a wrong value silently
   renders a 1px image.
3. **Verify the right channel**: on an opaque background, ink coverage lives in
   **RGB**, not alpha. Compare both; probe edges at 50% coverage.
4. **SVG rotation is clockwise-positive** (y-down): lean RIGHT = positive degrees.
   Check the direction against the reference, not your intuition.
5. **Windows has no ImageMagick/Inkscape**; `system32\convert.exe` is the disk-format tool, NOT ImageMagick — use resvg.
6. macOS `.icns` can only be produced on macOS (iconutil) — PNG+ICO only on Windows.
7. **When verification fails, suspect the verifier**: never re-type the builder's
   constants (cx, radii, colors) into a reference script — a typo fakes a convincing
   "construction bug". Import the builder's code instead.

## Reference

See [REFERENCE.md](REFERENCE.md) for measurement techniques, arc/sweep-flag math,
offset-polygon construction, ICO format, and the full verification protocol.
