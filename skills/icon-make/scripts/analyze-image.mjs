#!/usr/bin/env node
// analyze-image.mjs — reverse-engineer a reference icon/logo image.
// Usage: node analyze-image.mjs <image.png> [--rows 40] [--cols 40] [--ascii 56]
//
// Output (stdout):
//   - background color (quantized histogram mode, refined to exact mode)
//   - ink color (mode among pixels far from background)
//   - ink pixel count, bounding box
//   - per-row / per-column ink extents (for stroke weight, slant, terminals)
//   - ASCII preview
// The script only reports raw data — interpretation (slant angle, terminal style,
// design DNA) is the agent's job.
import { readFileSync } from 'node:fs';
import { decodePng } from './icon-lib.mjs';

const args = process.argv.slice(2);
const file = args.find(a => !a.startsWith('--'));
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 && args[i + 1] ? Number(args[i + 1]) : d; };
const nRows = opt('rows', 40), nCols = opt('cols', 40), asciiW = opt('ascii', 56);

if (!file) { console.error('usage: node analyze-image.mjs <image.png> [--rows 40] [--cols 40] [--ascii 56]'); process.exit(1); }

const img = decodePng(readFileSync(file));
const { w, h, data } = img;
const hex = c => '#' + c.map(v => v.toString(16).padStart(2, '0')).join('').toUpperCase();

// --- background color: 4-bit-quantized histogram mode, refined to exact mode ---
const q = (v) => v >> 4;
const buckets = new Map();
const bucketSamples = new Map();
for (let i = 0; i < data.length; i += 4) {
  if (data[i + 3] < 128) continue;
  const key = (q(data[i]) << 8) | (q(data[i + 1]) << 4) | q(data[i + 2]);
  buckets.set(key, (buckets.get(key) || 0) + 1);
  if (!bucketSamples.has(key)) bucketSamples.set(key, []);
  bucketSamples.get(key).push(i);
}
let bgKey = 0, bgN = 0;
for (const [k, n] of buckets) if (n > bgN) { bgN = n; bgKey = k; }
const exact = new Map();
for (const i of bucketSamples.get(bgKey)) {
  const key = (data[i] << 24) | (data[i + 1] << 16) | (data[i + 2] << 8);
  exact.set(key, (exact.get(key) || 0) + 1);
}
let bg = [0, 0, 0];
for (const [k, n] of exact) if (n === Math.max(...exact.values())) { bg = [(k >> 24) & 255, (k >> 16) & 255, (k >> 8) & 255]; break; }

// --- ink pixels: far from bg ---
const isInk = i => {
  if (data[i + 3] < 128) return false;
  return Math.hypot(data[i] - bg[0], data[i + 1] - bg[1], data[i + 2] - bg[2]) > 60;
};
const inkBuckets = new Map();
let minX = w, maxX = -1, minY = h, maxY = -1, inkN = 0;
for (let y = 0; y < h; y++) {
  for (let x = 0; x < w; x++) {
    const i = (y * w + x) * 4;
    if (!isInk(i)) continue;
    inkN++;
    if (x < minX) minX = x; if (x > maxX) maxX = x;
    if (y < minY) minY = y; if (y > maxY) maxY = y;
    const key = (data[i] << 24) | (data[i + 1] << 16) | (data[i + 2] << 8);
    inkBuckets.set(key, (inkBuckets.get(key) || 0) + 1);
  }
}
let ink = [0, 0, 0], inkBest = 0;
for (const [k, n] of inkBuckets) if (n > inkBest) { inkBest = n; ink = [(k >> 24) & 255, (k >> 16) & 255, (k >> 8) & 255]; }

console.log(`image: ${w} x ${h}`);
console.log(`background: ${hex(bg)}  (${(100 * bgN / (w * h)).toFixed(1)}% of opaque pixels)`);
console.log(`ink:        ${hex(ink)}  (${inkN} px, ${(100 * inkN / (w * h)).toFixed(1)}%)`);
console.log(`ink bbox:   x ${minX}..${maxX}  y ${minY}..${maxY}  (w=${maxX - minX + 1} h=${maxY - minY + 1})`);
console.log(`margins:    left ${minX}  right ${w - 1 - maxX}  top ${minY}  bottom ${h - 1 - maxY}`);

// --- row extents ---
console.log(`\nROW extents (sampled ${nRows}):`);
const rowStep = Math.max(1, Math.floor(h / nRows));
for (let y = 0; y < h; y += rowStep) {
  let l = -1, r = -1;
  for (let x = 0; x < w; x++) if (isInk((y * w + x) * 4)) { if (l < 0) l = x; r = x; }
  if (l >= 0) console.log(`  y=${String(y).padStart(4)}: L=${l} R=${r} w=${r - l + 1}`);
}

// --- column extents ---
console.log(`\nCOLUMN extents (sampled ${nCols}):`);
const colStep = Math.max(1, Math.floor(w / nCols));
for (let x = 0; x < w; x += colStep) {
  let t = -1, b = -1;
  for (let y = 0; y < h; y++) if (isInk((y * w + x) * 4)) { if (t < 0) t = y; b = y; }
  if (t >= 0) console.log(`  x=${String(x).padStart(4)}: T=${t} B=${b} h=${b - t + 1}`);
}

// --- ASCII preview ---
const aw = asciiW, ah = Math.max(1, Math.round(asciiW * h / w / 2));
const ramp = ' .:+#';
let out = '\nASCII preview (ink density):\n';
for (let gy = 0; gy < ah; gy++) {
  out += '  |';
  for (let gx = 0; gx < aw; gx++) {
    let sum = 0, n = 0;
    const y0 = Math.floor(gy * h / ah), y1 = Math.floor((gy + 1) * h / ah);
    const x0 = Math.floor(gx * w / aw), x1 = Math.floor((gx + 1) * w / aw);
    for (let y = y0; y < y1; y += 2) for (let x = x0; x < x1; x += 2) { sum += isInk((y * w + x) * 4) ? 1 : 0; n++; }
    const d = n ? sum / n : 0;
    out += ramp[Math.min(ramp.length - 1, Math.ceil(d * (ramp.length - 1)))];
  }
  out += '|\n';
}
console.log(out);
