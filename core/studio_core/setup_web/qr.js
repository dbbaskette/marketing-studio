'use strict';
// A small QR code encoder for Marketing Studio's private network link: byte mode, error
// correction level M, versions 1 to 10 (up to 213 bytes). Plain JavaScript, drawn on this
// computer; nothing is fetched, logged or sent anywhere. It follows ISO/IEC 18004, and
// tests/test_qr_code.py reads every code back with a decoder of its own.
(function (global) {
  // Error correction codewords per block, and blocks, for level M, by version 1 to 10.
  const ECC_PER_BLOCK = [10, 16, 26, 18, 24, 16, 18, 22, 22, 26];
  const BLOCKS = [1, 1, 1, 2, 2, 4, 4, 4, 5, 5];
  const MOST_VERSION = 10;
  const LEVEL_M = 0;   // the two format bits of level M

  function rawModules(version) {
    let result = (16 * version + 128) * version + 64;
    if (version >= 2) {
      const aligned = Math.floor(version / 7) + 2;
      result -= (25 * aligned - 10) * aligned - 55;
      if (version >= 7) result -= 36;
    }
    return result;
  }
  const dataCodewords = version => Math.floor(rawModules(version) / 8)
    - ECC_PER_BLOCK[version - 1] * BLOCKS[version - 1];

  function multiply(x, y) {
    let z = 0;
    for (let i = 7; i >= 0; i--) {
      z = (z << 1) ^ ((z >>> 7) * 0x11d);
      z ^= ((y >>> i) & 1) * x;
    }
    return z;
  }
  function divisor(degree) {
    const result = new Array(degree).fill(0);
    result[degree - 1] = 1;
    let root = 1;
    for (let i = 0; i < degree; i++) {
      for (let j = 0; j < degree; j++) {
        result[j] = multiply(result[j], root);
        if (j + 1 < degree) result[j] ^= result[j + 1];
      }
      root = multiply(root, 0x02);
    }
    return result;
  }
  function remainder(data, by) {
    const result = by.map(() => 0);
    for (const value of data) {
      const factor = value ^ result.shift();
      result.push(0);
      by.forEach((coefficient, i) => { result[i] ^= multiply(coefficient, factor); });
    }
    return result;
  }

  // The data codewords: mode, count, the bytes, a terminator and padding.
  function codewords(bytes, version) {
    const bits = [];
    const put = (value, length) => { for (let i = length - 1; i >= 0; i--) bits.push((value >>> i) & 1); };
    put(0b0100, 4);
    put(bytes.length, version <= 9 ? 8 : 16);
    for (const value of bytes) put(value, 8);
    const capacity = dataCodewords(version) * 8;
    put(0, Math.min(4, capacity - bits.length));
    put(0, (8 - bits.length % 8) % 8);
    for (let pad = 0xec; bits.length < capacity; pad ^= 0xec ^ 0x11) put(pad, 8);
    const result = [];
    for (let i = 0; i < bits.length; i += 8) result.push(bits.slice(i, i + 8).reduce((a, b) => (a << 1) | b, 0));
    return result;
  }
  function interleaved(data, version) {
    const blocks = BLOCKS[version - 1], ecc = ECC_PER_BLOCK[version - 1];
    const raw = Math.floor(rawModules(version) / 8);
    const short = blocks - raw % blocks, shortLength = Math.floor(raw / blocks);
    const by = divisor(ecc), made = [];
    for (let i = 0, k = 0; i < blocks; i++) {
      const part = data.slice(k, k + shortLength - ecc + (i < short ? 0 : 1));
      k += part.length;
      const check = remainder(part, by);
      if (i < short) part.push(0);
      made.push(part.concat(check));
    }
    const result = [];
    for (let i = 0; i < made[0].length; i++) {
      made.forEach((block, j) => { if (i !== shortLength - ecc || j >= short) result.push(block[i]); });
    }
    return result;
  }

  function alignments(version, size) {
    if (version === 1) return [];
    const count = Math.floor(version / 7) + 2;
    const step = Math.floor((version * 8 + count * 3 + 5) / (count * 4 - 4)) * 2;
    const result = [6];
    for (let at = size - 7; result.length < count; at -= step) result.splice(1, 0, at);
    return result;
  }
  const MASKS = [
    (x, y) => (x + y) % 2 === 0, (x, y) => y % 2 === 0, x => x % 3 === 0,
    (x, y) => (x + y) % 3 === 0, (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0,
    (x, y) => x * y % 2 + x * y % 3 === 0, (x, y) => (x * y % 2 + x * y % 3) % 2 === 0,
    (x, y) => ((x + y) % 2 + x * y % 3) % 2 === 0];

  function penalty(grid) {
    const size = grid.length;
    let score = 0, dark = 0;
    const lines = [];
    for (let i = 0; i < size; i++) {
      lines.push(grid[i]);
      lines.push(grid.map(row => row[i]));
    }
    const finder = [true, false, true, true, true, false, true];
    for (const line of lines) {
      for (let i = 0, run = 1; i < size; i++) {
        run = i > 0 && line[i] === line[i - 1] ? run + 1 : 1;
        if (run === 5) score += 3; else if (run > 5) score += 1;
      }
      for (let i = 0; i + 7 <= size; i++) {
        if (!finder.every((value, k) => line[i + k] === value)) continue;
        const before = i >= 4 && [1, 2, 3, 4].every(k => !line[i - k]);
        const after = i + 11 <= size && [7, 8, 9, 10].every(k => !line[i + k]);
        if (before || after) score += 40;
      }
    }
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        if (grid[y][x]) dark++;
        if (x < size - 1 && y < size - 1 && grid[y][x] === grid[y][x + 1]
          && grid[y][x] === grid[y + 1][x] && grid[y][x] === grid[y + 1][x + 1]) score += 3;
      }
    }
    const total = size * size;
    return score + (Math.ceil(Math.abs(dark * 20 - total * 10) / total) - 1) * 10;
  }

  // The modules of the code for `text`, dark as true, row by row; null when it is too long.
  function encode(text) {
    const bytes = [...new TextEncoder().encode(String(text))];
    let version = 1;
    while (version <= MOST_VERSION && 4 + (version <= 9 ? 8 : 16) + bytes.length * 8 > dataCodewords(version) * 8) version++;
    if (version > MOST_VERSION) return null;
    const size = version * 4 + 17;
    const grid = Array.from({length: size}, () => new Array(size).fill(false));
    const fixed = Array.from({length: size}, () => new Array(size).fill(false));
    const set = (x, y, dark) => { grid[y][x] = dark; fixed[y][x] = true; };
    for (let i = 0; i < size; i++) { set(6, i, i % 2 === 0); set(i, 6, i % 2 === 0); }
    for (const [cx, cy] of [[3, 3], [size - 4, 3], [3, size - 4]]) {
      for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) {
        const x = cx + dx, y = cy + dy, far = Math.max(Math.abs(dx), Math.abs(dy));
        if (x >= 0 && x < size && y >= 0 && y < size) set(x, y, far !== 2 && far !== 4);
      }
    }
    const places = alignments(version, size), last = places.length - 1;
    places.forEach((ax, i) => places.forEach((ay, j) => {
      if ((i === 0 && j === 0) || (i === 0 && j === last) || (i === last && j === 0)) return;
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) set(ax + dx, ay + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
    }));
    const format = mask => {
      const data = (LEVEL_M << 3) | mask;
      let rem = data;
      for (let i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
      const bits = ((data << 10) | rem) ^ 0x5412, bit = i => ((bits >>> i) & 1) === 1;
      for (let i = 0; i <= 5; i++) set(8, i, bit(i));
      set(8, 7, bit(6)); set(8, 8, bit(7)); set(7, 8, bit(8));
      for (let i = 9; i < 15; i++) set(14 - i, 8, bit(i));
      for (let i = 0; i < 8; i++) set(size - 1 - i, 8, bit(i));
      for (let i = 8; i < 15; i++) set(8, size - 15 + i, bit(i));
      set(8, size - 8, true);
    };
    format(0);
    if (version >= 7) {
      let rem = version;
      for (let i = 0; i < 12; i++) rem = (rem << 1) ^ ((rem >>> 11) * 0x1f25);
      const bits = (version << 12) | rem;
      for (let i = 0; i < 18; i++) {
        const dark = ((bits >>> i) & 1) === 1, a = size - 11 + i % 3, b = Math.floor(i / 3);
        set(a, b, dark); set(b, a, dark);
      }
    }
    const data = interleaved(codewords(bytes, version), version);
    let at = 0;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      for (let vertical = 0; vertical < size; vertical++) {
        for (let j = 0; j < 2; j++) {
          const x = right - j, upward = ((right + 1) & 2) === 0, y = upward ? size - 1 - vertical : vertical;
          if (!fixed[y][x] && at < data.length * 8) { grid[y][x] = ((data[at >>> 3] >>> (7 - (at & 7))) & 1) === 1; at++; }
        }
      }
    }
    const masked = mask => grid.map((row, y) => row.map((dark, x) => fixed[y][x] ? dark : dark !== MASKS[mask](x, y)));
    let best = 0, lowest = Infinity;
    for (let mask = 0; mask < 8; mask++) {
      format(mask);
      const score = penalty(masked(mask));
      if (score < lowest) { lowest = score; best = mask; }
    }
    format(best);
    return masked(best);
  }

  // The code as an SVG image, dark on light whatever the page's appearance so a camera reads
  // it, with a quiet zone of four modules. `label` is its text alternative.
  function svg(text, label) {
    const grid = encode(text);
    if (!grid) return null;
    const space = 'http://www.w3.org/2000/svg', size = grid.length + 8;
    const image = document.createElementNS(space, 'svg');
    for (const [name, value] of Object.entries({viewBox: `0 0 ${size} ${size}`, role: 'img',
      'aria-label': label, 'shape-rendering': 'crispEdges', class: 'qr-code'})) image.setAttribute(name, value);
    const ground = document.createElementNS(space, 'rect');
    for (const [name, value] of Object.entries({width: size, height: size, fill: '#fff'})) ground.setAttribute(name, value);
    const marks = document.createElementNS(space, 'path');
    let path = '';
    grid.forEach((row, y) => row.forEach((dark, x) => { if (dark) path += `M${x + 4} ${y + 4}h1v1h-1z`; }));
    marks.setAttribute('d', path); marks.setAttribute('fill', '#000');
    image.append(ground, marks);
    return image;
  }

  global.StudioQR = {encode, svg};
})(typeof window === 'undefined' ? globalThis : window);
