# REFERENCE.md — icon-make deep dive

Everything here was proven in a real session (Sun Reader icon, from a Turkish
"tabya" reference: `#FFC200` background, `#1E1E1D` ultra-bold geometric letter).
Read SKILL.md first; this file is the "why" and the math.

---

## 1. Reverse-engineering a reference image

`scripts/analyze-image.mjs` gives raw data. Turn it into design DNA:

| Measurement | How | Watch out for |
|---|---|---|
| Background color | histogram mode over opaque pixels (quantize to 4-bit/channel first, then refine to exact mode inside the winning bucket) | logos often have a 1px antialiased border; the mode is the true fill |
| Ink color | mode among pixels with color-distance > 60 from bg | two-tone logos have a secondary color — report both modes |
| Stroke weight | row extents where the glyph is a plain stroke (e.g. a stem): width ≈ stroke | at curves the row extent is wider than the perpendicular stroke — don't measure there |
| Slant | fit a line through one edge's extent samples (e.g. stem left edge at several heights) | **direction**: "top-right/bottom-left" = leans RIGHT. Always sanity-check against the rendered image |
| Terminals | look at each stroke end: flat butt cut, rounded corner, or tapered wedge | the reference's character usually lives here |
| Optical size | ink bbox + margins; reproduce the same box, not the same point size | an "S" is naturally wider than a "t" — match visual weight, not width |

For a curved terminal (e.g. a hooked top), scan the boundary densely
(per-column top-most ink) and fit a Bezier by eye — you only need 2–4 control
points; sub-pixel fidelity is pointless at icon sizes.

---

## 2. SVG construction techniques

### 2a. Stroked centerline (fast path)

Express the letter as one path with SVG arc commands, then let the renderer do
the offset math:

```svg
<path d="M T1x T1y A rx ry 0 largeArc sweep spineX spineY A rx ry 0 largeArc sweep T2x T2y"
      fill="none" stroke="#1E1E1D" stroke-width="175" stroke-linecap="butt"/>
```

Arc flags (SVG y-down coords — positive angles appear CLOCKWISE on screen):

- `large-arc=1` when the swept angle > 180°
- `sweep=1` = clockwise on screen; `sweep=0` = counterclockwise
- Example: an "S" as two arcs — bowl 1 runs from the upper-right terminal over
  the crown and down the left to the spine: counterclockwise on screen →
  `sweep=0`. Bowl 2 runs from the spine down the right, under the bottom, up the
  left: clockwise → `sweep=1`.
- `stroke-linecap="butt"` gives a flat cut perpendicular to the path direction —
  the classic geometric terminal.

Joining two arcs tangentially at a shared point (the spine) requires both arcs to
reach that point with the same tangent direction. Two circles stacked with the
same radius do this automatically: bowl 1's bottom point and bowl 2's top point
coincide at the spine, both with a horizontal tangent.

### 2b. Offset polygon (needed for tapered/pointed terminals)

A stroke cannot taper, so build the outline yourself:

1. Sample the centerline (bowl arcs) at ~900–1200 points (≈1px spacing).
2. At each sample compute the tangent from central differences, then the unit
   normal `n = (-ty, tx)`.
3. Offset both sides: `O = P + n·h`, `I = P - n·h`, with `h = w/2`.
4. **Taper**: for the last `taperLen` px of arc length, `h = (w/2)·t^pow` where
   `t` = remaining distance / taperLen (t=0 at the tip → h=0 → a sharp point;
   pow ≈ 0.7 gives a slightly convex, leaf-like sweep).
5. Polygon = outer side forward + inner side reversed + implicit close (the top
   cap is the straight closing edge = a butt cut).
6. Simplify with Douglas-Peucker (eps ≈ 0.4px) before emitting — a 2400-point
   outline collapses to ~140 points and renders identically.

Optional: extend the tip beyond the arc's end with a straight segment along the
end tangent (`tipExt`). Usually unnecessary — prefer arc extension.

**Verify the polygon against the stroked render** (see §4) before trusting it.

### 2c. Rotation

`transform="rotate(deg cx cy)"` with positive deg = **clockwise** (y-down coords).
A letter whose top tilts right ("italic") uses POSITIVE degrees. Getting this
backwards is the most common direction bug — always compare against the
reference image, not intuition.

### 2d. Corners & transparency

- Rounded corners: `rx`/`ry` on the background `<rect>`. 22% of canvas (≈229px
  at 1024) reads as iOS-squircle-ish; 30px on 1024 is nearly square — clarify
  with the user which they mean ("30px" may come from a CSS border-radius habit).
- Leave everything outside the rect **transparent** (alpha 0) so the OS/app can
  place the icon on any surface. resvg: `background: 'rgba(0,0,0,0)'`.

---

## 3. Rasterization & packaging

### resvg

```js
import { Resvg } from '@resvg/resvg-js';
const r = new Resvg(svg, { fitTo: { mode: 'width', value: 1024 }, background: 'rgba(0,0,0,0)' });
const png = r.render().asPng();
```

- Install with `npm install @resvg/resvg-js` in a dir that HAS its own
  package.json (see Traps). No native build step; prebuilt binaries.
- `fitTo.width` must be the SVG's own width for fixed-size SVGs — passing a wrong
  value (e.g. 1) silently produces a 1px image.
- The skill's scripts resolve resvg from **cwd** (`require.resolve` with
  `paths: [cwd, ...NODE_PATH]`), so they run from the tooling dir regardless of
  where they live.

### ICO format (write it yourself — no tooling needed)

```
header:  00 00 01 00 <count:u16LE>          # reserved, type 1 (icon), count
entry:   <w:u8> <h:u8> <colors:u8=0> <rsv:u8=0> <planes:u16LE=1> <bpp:u16LE=32>
         <payloadSize:u32LE> <offset:u32LE>
payload: a complete PNG file per entry
```

- Size 256 is stored as `0` in the width/height bytes.
- PNG-compressed entries are standard since Vista; electron-builder/rcedit read
  them fine. (GDI+ `System.Drawing.Icon` may fall back to 128 when asked for 256
  — a GDI+ quirk, not a file bug; verify by parsing the directory instead.)
- Standard set: 16, 24, 32, 48, 64, 128, 256.

### Other platforms

- macOS `.icns`: only via `iconutil` on a Mac. On Windows, deliver PNG (+ICO) and
  note that mac packaging must run on macOS.
- electron-builder picks up `build/icon.png` by default and `build/icon.ico` for
  Windows; a window icon set via `new BrowserWindow({ icon })` updates on next
  app start, but installer/taskbar-pinned icons need a full rebuild.

---

## 4. Verification protocol (never skip)

Order matters — cheapest and most structural first:

1. **Construction equivalence**: render the offset-polygon version and the stroked-arc
   version at 1024 and `diffPng` them. Expect a thin antialiasing band: an exact
   polygon ≈ 0.2% of pixels (~1970/1M), an RDP-simplified one (eps 0.4) ≈ the same
   (~0.18% — simplification is free). Investigate anything larger.
2. **Edge probes**: `topInkRow`/`coverageAt` at 50% threshold on several columns
   of both renders; they should agree within 1px.
3. **Alpha vs RGB — the classic trap**: on an OPAQUE background, ink coverage is
   blended into **RGB**; alpha stays 255 everywhere inside the background rect.
   A diff that only checks alpha will report "identical" for two different
   letters. Always diff both channels. (Transparency checks belong at the
   corners: alpha must be 0 outside the rounded rect.)
4. **Exact colors**: corner/edge pixel = exact bg RGB; letter interior = exact
   ink RGB.
5. **ICO directory**: parse entries, assert declared size == payload PNG size.
6. **Small-size strip**: render 256/128/96/64/48/32/24/16 on a dark strip and
   look. Ultra-bold glyphs lose their counters below ~32px — acceptable for
   icons, but say so.
7. **Install**: stage outside the target, get user approval, copy, then compare
   file hashes staged-vs-installed.

### When verification FAILS: suspect the verifier first

Real incident: a "7px crown deviation" between the polygon and a hand-written
stroked reference turned out to be a **typo in the reference script** — it used
`cx = 500` while the builder used `cx = canvas/2 = 512`. A 12px center offset
mimics a construction bug perfectly (max deviation appears on steep edge
slopes, zero at the crown — a convincing pattern).

Rules that fall out of this:
- **Never re-type geometry constants into a verification script.** Import the
  builder's own functions/constants, or derive the reference from the builder's
  output. Hand-copied numbers drift.
- Cross-check with an **independent decoder** (e.g. PowerShell + System.Drawing
  on Windows) when two of your own tools disagree — it arbitrates render vs
  probe bugs, though not vs a wrong reference.
- Sanity-check your analytic model against a THIRD construction (e.g. sample the
  true concentric circles directly into a path). If all three of *your*
  constructions agree and only the hand-written model disagrees, the model is
  what's wrong.

---

## 5. The review loop (how to not waste the user's time)

- **Direction first, details later.** Round 1: a matrix of 3–5 variants that
  differ on the axes the user actually cares about (slant? corner size? terminal
  style? weight?), as ONE contact-sheet image with labels. Use `ask_user_question`
  with concrete options — users pick from examples far more reliably than from
  prose.
- **Then fine-tune parameters.** Each round should be a parameter change
  (taper 140→220, rot 8→10), never a redraw.
- **Show the reference-derived numbers** (colors, weights) so the user can
  correct your reading of the original.
- **Present small-size legibility early** — it constrains how bold you can go.
- Never install into the project before explicit approval; never delete the
  previous icon until the new one is approved (keep the reference + old asset
  untouched).

---

## 6. Traps, expanded

1. **npm walks up the tree.** `npm install X` in a directory without its own
   `package.json` finds the nearest ancestor package.json — inside a project,
   that means: X added to the project's dependencies, an npm `package-lock.json`
   created next to a pnpm lockfile, `node_modules/.package-lock.json` created,
   and extraneous packages pruned from the project's tree. Recovery:
   `git checkout package.json`, delete the npm lockfiles, remove the installed
   package from node_modules, then `pnpm install --frozen-lockfile` (or the
   project's package manager) and run the project's type check/tests to confirm.
   Prevention: `npm init -y` first, or keep tooling outside the repo.
2. **resvg width** — see §3.
3. **Alpha-vs-RGB verification** — see §4.3.
4. **SVG rotation direction** — see §2c.
5. **Windows `convert`** — `C:\Windows\system32\convert.exe` is the FAT→NTFS
   disk utility, NOT ImageMagick's convert. There is no system ImageMagick,
   Inkscape, or rsvg on a default Windows box; use resvg (or Edge/Chrome
   headless screenshots of an HTML-wrapped SVG as a fallback).
6. **Corner radius units** — confirm what the user means by "30px" (at which
   canvas size?) before baking it in.
7. **Verification references must come from the builder, not from memory.** A
   hand-written reference that re-types a constant (cx=500 vs the builder's
   512) produces a fake "construction bug" with a convincing signature (max
   deviation on steep slopes, zero at the crown). Import the builder's code;
   if verification fails, doubt the verifier before the construction.
