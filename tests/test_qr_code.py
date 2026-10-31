"""The QR code for the private network link reads back as exactly that link.

core/studio_core/setup_web/qr.js draws it in the page. This test runs the encoder in Node.js
and reads each code back with a small, separate decoder written from ISO/IEC 18004's tables:
format and version information, the function patterns, the mask, the block layout, the
Reed-Solomon check and the byte-mode data. Synthetic links only.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENCODER = ROOT / 'core/studio_core/setup_web/qr.js'
# Level M: (blocks of one length, data codewords) groups and ECC codewords per block, v1-10.
BLOCKS_M = {1: ([(1, 16)], 10), 2: ([(1, 28)], 16), 3: ([(1, 44)], 26), 4: ([(2, 32)], 18),
            5: ([(2, 43)], 24), 6: ([(4, 27)], 16), 7: ([(4, 31)], 18),
            8: ([(2, 38), (2, 39)], 22), 9: ([(3, 36), (2, 37)], 22),
            10: ([(4, 43), (1, 44)], 26)}
ALIGNMENT = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
             7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}
MASKS = [lambda i, j: (i + j) % 2 == 0, lambda i, j: i % 2 == 0, lambda i, j: j % 3 == 0,
         lambda i, j: (i + j) % 3 == 0, lambda i, j: (i // 2 + j // 3) % 2 == 0,
         lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
         lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
         lambda i, j: ((i + j) % 2 + (i * j) % 3) % 2 == 0]


def gf_tables():
    exp, log, value = [0] * 512, [0] * 256, 1
    for power in range(255):
        exp[power], log[value] = value, power
        value <<= 1
        if value & 0x100:
            value ^= 0x11d
    for power in range(255, 512):
        exp[power] = exp[power - 255]
    return exp, log


EXP, LOG = gf_tables()


def syndromes(codeword, ecc):
    """c(α^i) for i below `ecc`: all zero when the block is a valid Reed-Solomon code word."""
    found = []
    for i in range(ecc):
        total = 0
        for value in codeword:
            total = (EXP[LOG[total] + i] if total else 0) ^ value
        found.append(total)
    return found


def bch_ok(value, bits, generator):
    for shift in range(bits - 1, -1, -1):
        if value >> (shift + generator.bit_length() - 1) & 1:
            value ^= generator << shift
    return value == 0


def decode(grid):
    size = len(grid)
    version = (size - 17) // 4
    assert size == version * 4 + 17 and 1 <= version <= 10, size
    module = lambda row, column: grid[row][column]
    # Format information: the copy around the top-left finder, then the split copy.
    first = [module(i, 8) for i in range(6)] + [module(7, 8), module(8, 8), module(8, 7)] + \
            [module(8, 14 - i) for i in range(9, 15)]
    second = [module(8, size - 1 - i) for i in range(8)] + [module(size - 15 + i, 8) for i in range(8, 15)]
    assert first == second, 'the two copies of the format information differ'
    value = sum(bit << i for i, bit in enumerate(first)) ^ 0x5412
    assert bch_ok(value, 5, 0x537), 'format information fails its BCH check'
    level, mask = value >> 13, (value >> 10) & 7
    assert level == 0, 'level M'
    assert module(size - 8, 8), 'the dark module'
    reserved = [[False] * size for _ in range(size)]

    def keep(row, column):
        if 0 <= row < size and 0 <= column < size:
            reserved[row][column] = True
    for top, left in ((0, 0), (0, size - 8), (size - 8, 0)):
        for row in range(top, top + 8):
            for column in range(left, left + 8):
                keep(row, column)
    for i in range(size):
        keep(6, i)
        keep(i, 6)
    centres = ALIGNMENT[version]
    # Every pair of centres, except the three that would sit on a finder pattern.
    for row in centres:
        for column in centres:
            if {row, column} <= {6} or (row == 6 and column == centres[-1]) \
                    or (column == 6 and row == centres[-1]):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    keep(row + dr, column + dc)
    for i in range(9):
        keep(8, i)
        keep(i, 8)
    for i in range(8):
        keep(8, size - 1 - i)
        keep(size - 1 - i, 8)
    if version >= 7:
        bits = [module(i // 3, size - 11 + i % 3) for i in range(18)]
        assert bits == [module(size - 11 + i % 3, i // 3) for i in range(18)]
        value = sum(bit << i for i, bit in enumerate(bits))
        assert value >> 12 == version and bch_ok(value, 6, 0x1f25), 'version information'
        for i in range(18):
            keep(i // 3, size - 11 + i % 3)
            keep(size - 11 + i % 3, i // 3)
    # The data modules, two columns at a time from the right, up then down.
    stream, column, upward = [], size - 1, True
    while column > 0:
        if column == 6:
            column -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for c in (column, column - 1):
                if not reserved[row][c]:
                    stream.append(module(row, c) != MASKS[mask](row, c))
        column -= 2
        upward = not upward
    groups, ecc = BLOCKS_M[version]
    lengths = [length for count, length in groups for _ in range(count)]
    total = sum(lengths) + ecc * len(lengths)
    words = [int(''.join('1' if bit else '0' for bit in stream[i * 8:i * 8 + 8]), 2) for i in range(total)]
    blocks, at = [[] for _ in lengths], 0
    for i in range(max(lengths)):
        for b, length in enumerate(lengths):
            if i < length:
                blocks[b].append(words[at])
                at += 1
    checks = [[] for _ in lengths]
    for i in range(ecc):
        for b in range(len(lengths)):
            checks[b].append(words[at])
            at += 1
    for data, check in zip(blocks, checks):
        assert not any(syndromes(data + check, ecc)), 'a block fails its Reed-Solomon check'
    bits = ''.join(f'{word:08b}' for data in blocks for word in data)
    assert bits[:4] == '0100', 'byte mode'
    count_bits = 8 if version <= 9 else 16
    count = int(bits[4:4 + count_bits], 2)
    start = 4 + count_bits
    return bytes(int(bits[start + i * 8:start + i * 8 + 8], 2) for i in range(count)).decode('utf-8')


@unittest.skipUnless(shutil.which('node'), 'The QR code check needs Node.js.')
class QRCodeTests(unittest.TestCase):
    LINKS = ['http://192.168.1.23:54321/#token=' + 'Ab9_-' * 9,       # the usual private link
             'http://10.0.0.2:8000/#token=' + 'k' * 43,
             'h', 'http://172.16.0.9:65535/#token=' + 'Zz0' * 40]   # version 7 or more

    def encode(self, texts):
        script = r'''const fs = require('node:fs'), vm = require('node:vm');
const context = {TextEncoder};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const made = JSON.parse(process.argv[2]).map(text => context.StudioQR.encode(text));
const nodes = [];
const node = tag => { const made = {tag, attributes: {}, children: [], setAttribute(name, value) { this.attributes[name] = String(value); }, append(...more) { this.children.push(...more); }}; return made; };
context.document = {createElementNS: (space, tag) => node(tag)};
const image = context.StudioQR.svg(JSON.parse(process.argv[2])[0], 'QR code for the private session link');
process.stdout.write(JSON.stringify({made, image: image.attributes, parts: image.children.map(part => part.attributes),
  long: context.StudioQR.encode('x'.repeat(214))}));
'''
        done = subprocess.run(['node', '-e', script, str(ENCODER), json.dumps(texts)],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_each_code_decodes_to_exactly_its_link(self):
        found = self.encode(self.LINKS)
        sizes = []
        for text, grid in zip(self.LINKS, found['made']):
            with self.subTest(text=text[:30]):
                self.assertEqual(decode(grid), text)
                sizes.append(len(grid))
        self.assertGreaterEqual(max(sizes), 7 * 4 + 17, 'a version with version information was read')
        self.assertIsNone(found['long'], 'a text too long for version 10 is not drawn')

    def test_the_image_has_a_text_alternative_and_reads_in_any_appearance(self):
        found = self.encode(self.LINKS[:1])
        self.assertEqual(found['image']['role'], 'img')
        self.assertEqual(found['image']['aria-label'], 'QR code for the private session link')
        ground, marks = found['parts']
        self.assertEqual((ground['fill'], marks['fill']), ('#fff', '#000'))
        source = ENCODER.read_text().replace("'http://www.w3.org/2000/svg'", '')
        for forbidden in ('fetch(', 'XMLHttpRequest', 'console.', 'import(', 'http://', 'https://'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
