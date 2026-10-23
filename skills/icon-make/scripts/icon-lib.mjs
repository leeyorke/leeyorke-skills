// icon-lib.mjs — shared utilities for the icon-make skill.
// PNG decode/encode, SVG→PNG render (resvg), ICO packing, pixel diff, RDP simplify.
//
// resvg is resolved from the CURRENT WORKING DIRECTORY's node_modules (or NODE_PATH),
// so these scripts work from any location. Run them from a directory where you did:
//   npm init -y && npm install @resvg/resvg-js
import { inflateSync, deflateSync } from 'node:zlib';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

// ---------- resvg loader (cwd-relative, never walks up into a project) ----------
let _Resvg = null;
export async function getResvg() {
  if (_Resvg) return _Resvg;
  const require = createRequire(import.meta.url);
  const paths = [process.cwd(), ...(process.env.NODE_PATH || '').split(';').filter(Boolean)];
  let resolved;
  try {
    resolved = require.resolve('@resvg/resvg-js', { paths });
  } catch {
    throw new Error(
      '@resvg/resvg-js not found from cwd. In your working directory run:\n' +
      '  npm init -y && npm install @resvg/resvg-js\n' +
      'NEVER run npm install in a directory that has NO package.json inside a project:\n' +
      'npm walks up the tree and pollutes the project\'s package.json + node_modules.'
    );
  }
  const m = await import(pathToFileURL(resolved).href);
  _Resvg = m.Resvg || m.default?.Resvg || m.default;
  return _Resvg;
}

// Render an SVG string to a PNG buffer at the given pixel width.
export async function renderSvg(svg, width) {
  const Resvg = await getResvg();
  const r = new Resvg(svg, {
    fitTo: { mode: 'width', value: width }, // pass the SVG's OWN width for fixed-size SVGs — a wrong value silently yields a tiny image
    background: 'rgba(0,0,0,0)',
  });
  return r.render().asPng();
}

// ---------- PNG decode (filters 0-4; color types 0/2/4/6) ----------
export function decodePng(buf) {
  let pos = 8;
  const idat = [];
  let w = 0, h = 0, ct = 0;
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString('ascii', pos + 4, pos + 8);
    const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') {
      w = data.readUInt32BE(0); h = data.readUInt32BE(4);
      ct = data[9];
    } else if (type === 'IDAT') idat.push(data);
    pos += 12 + len;
  }
  if (ct === 3) throw new Error('palette PNG not supported — re-encode as RGBA/RGB first');
  const ch = ct === 6 ? 4 : ct === 2 ? 3 : ct === 4 ? 2 : 1;
  const gray = ch === 1 || ch === 2;
  const stride = w * ch;
  const raw = inflateSync(Buffer.concat(idat));
  const out = Buffer.alloc(h * stride);
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)];
    const row = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    const cur = Buffer.alloc(stride);
    for (let x = 0; x < stride; x++) {
      const a = x >= ch ? cur[x - ch] : 0, b = prev[x], c = x >= ch ? prev[x - ch] : 0;
      let v = row[x];
      if (f === 1) v = (v + a) & 255;
      else if (f === 2) v = (v + b) & 255;
      else if (f === 3) v = (v + ((a + b) >> 1)) & 255;
      else if (f === 4) {
        const pp = a + b - c, pa = Math.abs(pp - a), pb = Math.abs(pp - b), pc = Math.abs(pp - c);
        v = (v + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c)) & 255;
      }
      cur[x] = v;
    }
    cur.copy(out, y * stride);
    prev = cur;
  }
  // normalize to RGBA
  const rgba = Buffer.alloc(h * w * 4);
  for (let i = 0, j = 0; i < rgba.length; i += 4, j += ch) {
    if (gray) {
      const g = out[j];
      rgba[i] = g; rgba[i + 1] = g; rgba[i + 2] = g;
      rgba[i + 3] = ch === 2 ? out[j + 1] : 255;
    } else {
      rgba[i] = out[j]; rgba[i + 1] = out[j + 1]; rgba[i + 2] = out[j + 2];
      rgba[i + 3] = ch === 4 ? out[j + 3] : 255;
    }
  }
  return { w, h, ch: 4, data: rgba };
}

// ---------- PNG encode (RGBA, filter 0) ----------
export function encodePng(img) {
  const { w, h, data } = img;
  const ch = 4, stride = w * ch;
  const raw = Buffer.alloc(h * (stride + 1));
  for (let y = 0; y < h; y++) {
    raw[y * (stride + 1)] = 0;
    data.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 6; // 8-bit RGBA
  const crcTable = [];
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
    crcTable[n] = c;
  }
  const mkChunk = (type, data) => {
    const l = Buffer.alloc(4); l.writeUInt32BE(data.length);
    const t = Buffer.from(type, 'ascii');
    const body = Buffer.concat([t, data]);
    let c = ~0;
    for (const b of body) c = crcTable[(c ^ b) & 0xFF] ^ (c >>> 8);
    const crc = Buffer.alloc(4); crc.writeUInt32BE((~c) >>> 0);
    return Buffer.concat([l, t, data, crc]);
  };
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
    mkChunk('IHDR', ihdr),
    mkChunk('IDAT', deflateSync(raw)),
    mkChunk('IEND', Buffer.alloc(0)),
  ]);
}

// ---------- ICO packing (PNG payloads; size 256 is stored as 0) ----------
export function packIco(sizes) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2); // type 1 = icon
  header.writeUInt16LE(sizes.length, 4);
  let offset = 6 + 16 * sizes.length;
  const entries = [], payloads = [];
  for (const s of sizes) {
    const e = Buffer.alloc(16);
    e[0] = s.size >= 256 ? 0 : s.size;
    e[1] = s.size >= 256 ? 0 : s.size;
    e[2] = 0; e[3] = 0;
    e.writeUInt16LE(1, 4);   // color planes
    e.writeUInt16LE(32, 6);  // bpp
    e.writeUInt32LE(s.data.length, 8);
    e.writeUInt32LE(offset, 12);
    entries.push(e); payloads.push(s.data);
    offset += s.data.length;
  }
  return Buffer.concat([header, ...entries, ...payloads]);
}

// Parse an ICO directory and verify every entry's declared size vs its PNG payload.
export function verifyIco(buf) {
  const count = buf.readUInt16LE(4);
  const out = [];
  for (let i = 0; i < count; i++) {
    const e = buf.subarray(6 + i * 16, 6 + (i + 1) * 16);
    const declared = (e[0] === 0 ? 256 : e[0]);
    const size = e.readUInt32LE(8), off = e.readUInt32LE(12);
    const png = buf.subarray(off, off + size);
    const isPng = png[0] === 0x89 && png[1] === 0x50;
    const actual = isPng ? png.readUInt32BE(16) : -1;
    out.push({ declared, actual, isPng, ok: isPng && actual === declared });
  }
  return out;
}

// ---------- pixel diff ----------
// IMPORTANT: on an OPAQUE background, ink coverage shows up in RGB, not alpha.
// Always compare BOTH channels (see REFERENCE.md §Verification).
export function diffPng(a, b) {
  if (a.w !== b.w || a.h !== b.h) throw new Error(`size mismatch ${a.w}x${a.h} vs ${b.w}x${b.h}`);
  let alphaDiff = 0, rgbDiff = 0, maxDelta = 0;
  for (let i = 0; i < a.data.length; i += 4) {
    const da = Math.abs(a.data[i + 3] - b.data[i + 3]);
    const dr = Math.abs(a.data[i] - b.data[i]);
    if (da > 8) alphaDiff++;
    if (dr > 8) rgbDiff++;
    if (dr > maxDelta) maxDelta = dr;
  }
  return { total: a.w * a.h, alphaDiff, rgbDiff, maxDelta };
}

// Ink coverage fraction (0..1) at a pixel, given the background and ink RGB.
export function coverageAt(img, x, y, bg, ink) {
  const i = (y * img.w + x) * 4;
  const lbg = Math.hypot(img.data[i] - bg[0], img.data[i + 1] - bg[1], img.data[i + 2] - bg[2]);
  const link = Math.hypot(img.data[i] - ink[0], img.data[i + 1] - ink[1], img.data[i + 2] - ink[2]);
  if (lbg + link === 0) return 0;
  return lbg / (lbg + link);
}

// Topmost row where ink coverage exceeds `thr` in a column (edge probe).
export function topInkRow(img, x, y0, y1, bg, ink, thr = 0.5) {
  for (let y = y0; y < y1; y++) if (coverageAt(img, x, y, bg, ink) > thr) return y;
  return -1;
}

// ---------- Douglas-Peucker polyline simplification ----------
function perpDist(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy;
  if (l2 === 0) return Math.hypot(p[0] - a[0], p[1] - a[1]);
  let t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}
export function rdp(pts, eps) {
  if (pts.length < 3) return pts.slice();
  const keep = new Array(pts.length).fill(false);
  keep[0] = keep[pts.length - 1] = true;
  const stack = [[0, pts.length - 1]];
  while (stack.length) {
    const [s, e] = stack.pop();
    let maxD = 0, idx = -1;
    for (let i = s + 1; i < e; i++) {
      const d = perpDist(pts[i], pts[s], pts[e]);
      if (d > maxD) { maxD = d; idx = i; }
    }
    if (idx > -1 && maxD > eps) {
      keep[idx] = true;
      stack.push([s, idx], [idx, e]);
    }
  }
  return pts.filter((_, i) => keep[i]);
}

export function fmt(n) { return Number(n.toFixed(2)); }
