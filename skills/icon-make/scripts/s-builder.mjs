#!/usr/bin/env node
// s-builder.mjs — worked example for icon-make: an ultra-bold geometric S built from
// two circular arcs (centerline), rendered as a variable-width filled outline with a
// tapered pointed tail. All parameters are CLI-overridable.
//
// Usage (from a dir with @resvg/resvg-js installed):
//   node s-builder.mjs [outDir] [--w 175] [--rx 131] [--ry 131] [--top 162] [--bottom 861]
//                     [--theta1 50] [--theta2 50] [--taper 140] [--pow 0.72] [--ext 0]
//                     [--rot 8] [--corner 229] [--bg '#FFC200'] [--ink '#1E1E1D'] [--sizes 16,32,256,1024]
//
// Technique notes (see REFERENCE.md):
//  - centerline = bowl1 arc (theta1 -> 90deg, counterclockwise on screen) + bowl2 arc
//    (-90deg -> 180-theta2, clockwise on screen), joined tangentially at the spine.
//  - the outline is the centerline offset by +/- w/2 along sampled normals; the width
//    tapers to 0 over the last `taper` px of arc length, producing the pointed tail.
//  - SVG rotation is CLOCKWISE for positive degrees (y-down coords): lean RIGHT = +rot.
import { writeFileSync, mkdirSync } from 'node:fs';
import { renderSvg, rdp } from './icon-lib.mjs';

const args = process.argv.slice(2);
const outDir = args.find(a => !a.startsWith('--')) || '.';
const num = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 && args[i + 1] ? Number(args[i + 1]) : d; };
const str = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 && args[i + 1] ? args[i + 1] : d; };

const CANVAS = 1024;
const P = {
  rx: num('rx', 131), ry: num('ry', 131), w: num('w', 175),
  top: num('top', 162), bottom: num('bottom', 861),
  theta1Deg: num('theta1', 50), theta2Deg: num('theta2', 50),
  taperLen: num('taper', 140), taperPow: num('pow', 0.72), tipExt: num('ext', 0), N: 1200,
};
const ROT = num('rot', 8);
const CORNER = num('corner', 229);
const BG = str('bg', '#FFC200');
const INK = str('ink', '#1E1E1D');
const SIZES = str('sizes', '16,24,32,48,64,128,256,512,1024').split(',').map(Number);

// ---------- centerline -> offset ring with taper ----------
function sRing(p, canvas = CANVAS) {
  const { rx, ry, w, top, bottom, theta1Deg, theta2Deg, taperLen, taperPow = 0.72, N } = p;
  const spineY = (top + bottom) / 2;
  const cy1 = spineY - ry, cy2 = spineY + ry;
  const cx = canvas / 2;
  const th1 = (theta1Deg * Math.PI) / 180;
  const pts = [];
  const half = Math.round(N / 2);
  for (let i = 0; i <= half; i++) {
    const t = -th1 - (Math.PI * 1.2222) * (i / half); // bowl 1: 220deg
    pts.push([cx + rx * Math.cos(t), cy1 + ry * Math.sin(t)]);
  }
  const th2 = (theta2Deg * Math.PI) / 180;
  const sweep2 = Math.PI * 1.5 - th2;
  for (let i = 1; i <= half; i++) {
    const t = -Math.PI / 2 + sweep2 * (i / half);
    pts.push([cx + rx * Math.cos(t), cy2 + ry * Math.sin(t)]);
  }
  if (p.tipExt > 0) {
    const a = pts[pts.length - 2], b = pts[pts.length - 1];
    let dx = b[0] - a[0], dy = b[1] - a[1];
    const l = Math.hypot(dx, dy); dx /= l; dy /= l;
    pts.push([b[0] + dx * p.tipExt, b[1] + dy * p.tipExt]);
  }
  const n = pts.length;
  const cum = [0];
  for (let i = 1; i < n; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const total = cum[n - 1];
  const hw = w / 2;
  const ring = [];
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
    let tx = b[0] - a[0], ty = b[1] - a[1];
    const l = Math.hypot(tx, ty) || 1; tx /= l; ty /= l;
    const nx = -ty, ny = tx;
    let h = hw;
    const d = total - cum[i];
    if (d < taperLen) h = hw * Math.pow(Math.max(0, d / taperLen), taperPow);
    ring.push([pts[i][0] + nx * h, pts[i][1] + ny * h], [pts[i][0] - nx * h, pts[i][1] - ny * h]);
  }
  return ring;
}

// ---------- build the SVG ----------
function buildSvg(p, { canvas = CANVAS, corner = CORNER, rot = ROT, bg = BG, ink = INK, simplify = 0.4 } = {}) {
  const ring = sRing(p, canvas);
  const loop = [];
  for (let i = 0; i < ring.length; i += 2) loop.push(ring[i]);       // outer side
  for (let i = ring.length - 1; i >= 0; i -= 2) loop.push(ring[i]);  // inner side, reversed
  const simple = simplify > 0 ? rdp(loop, simplify) : loop;
  const d = `M ${simple[0][0].toFixed(1)} ${simple[0][1].toFixed(1)} ` +
    simple.slice(1).map(q => `L ${q[0].toFixed(1)} ${q[1].toFixed(1)}`).join(' ') + ' Z';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${canvas}" height="${canvas}" viewBox="0 0 ${canvas} ${canvas}">
  <rect x="0" y="0" width="${canvas}" height="${canvas}" rx="${corner}" ry="${corner}" fill="${bg}"/>
  <g transform="rotate(${rot} ${canvas / 2} ${canvas / 2})">
    <path d="${d}" fill="${ink}"/>
  </g>
</svg>
`;
}

// ---------- emit ----------
mkdirSync(outDir, { recursive: true });
const svg = buildSvg(P);
writeFileSync(`${outDir}/icon.svg`, svg);
console.log('params:', JSON.stringify({ ...P, rot: ROT, corner: CORNER, bg: BG, ink: INK }));
console.log(`wrote ${outDir}/icon.svg`);

const { packIco } = await import('./icon-lib.mjs');
const pngs = {};
for (const s of SIZES) {
  pngs[s] = await renderSvg(svg, s);
  writeFileSync(`${outDir}/icon-${s}.png`, pngs[s]);
  console.log(`wrote ${outDir}/icon-${s}.png (${pngs[s].length} B)`);
}
const icoSizes = SIZES.filter(s => s <= 256);
if (icoSizes.length) {
  const ico = packIco(icoSizes.map(s => ({ size: s, data: pngs[s] })));
  writeFileSync(`${outDir}/icon.ico`, ico);
  console.log(`wrote ${outDir}/icon.ico (${ico.length} B, sizes ${icoSizes.join('/')})`);
}
