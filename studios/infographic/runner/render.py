"""Disposable Chromium rendering spike; no browser download or provider work.

This renders only a validated, self-contained SVG. The caller explicitly supplies
an installed headless executable and a new output folder. Production scene and
export orchestration remain later milestones.
"""
from __future__ import annotations

import base64
import html
import json
import math
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from .validation import image_size

SVG = 'http://www.w3.org/2000/svg'
MAX_SVG_BYTES = 46_000_000  # A bounded 32 MB raster expands when embedded as base64.
TAGS = {'svg', 'g', 'defs', 'clipPath', 'rect', 'circle', 'ellipse', 'line', 'polyline',
        'polygon', 'path', 'text', 'tspan', 'image', 'title', 'desc'}
ATTRS = {'id', 'viewBox', 'width', 'height', 'x', 'y', 'x1', 'x2', 'y1', 'y2', 'cx', 'cy',
         'r', 'rx', 'ry', 'd', 'points', 'fill', 'stroke', 'stroke-width', 'opacity',
         'fill-opacity', 'stroke-opacity', 'transform', 'font-family', 'font-size',
         'font-weight', 'text-anchor', 'dominant-baseline', 'dx', 'dy', 'href',
         'preserveAspectRatio', 'data-box', 'data-id', 'role', 'aria-label', 'clip-path'}


def safe_svg(text: str) -> str:
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_SVG_BYTES:
        raise ValueError('The SVG exceeds the rendering limit.')
    if '<!' in text or '<?' in text:
        raise ValueError('The SVG must not contain declarations or external entities.')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as failure:
        raise ValueError('The SVG cannot be read.') from failure
    if root.tag != '{' + SVG + '}svg':
        raise ValueError('Give one SVG document.')
    try:
        viewbox = [float(v) for v in root.get('viewBox', '').split()]
    except ValueError as failure:
        raise ValueError('The SVG needs a finite page viewBox.') from failure
    if len(viewbox) != 4 or not all(math.isfinite(v) for v in viewbox) \
            or viewbox[:2] != [0, 0] or min(viewbox[2:]) <= 0:
        raise ValueError('The SVG needs a finite positive page viewBox starting at zero.')
    clips = {element.get('id') for element in root.iter() if element.tag == '{' + SVG + '}clipPath'}
    for element in root.iter():
        if not element.tag.startswith('{' + SVG + '}') or element.tag.split('}', 1)[1] not in TAGS:
            raise ValueError('The SVG contains an unsupported element.')
        if element.tag.endswith('}image') and not element.get('href'):
            raise ValueError('Every SVG image needs an embedded reference.')
        for key, value in element.attrib.items():
            if key == 'clip-path':
                match = re.fullmatch(r'url\(#([A-Za-z][A-Za-z0-9_-]{0,100})\)', value)
                if not match or match[1] not in clips:
                    raise ValueError('An artwork clip must name an existing internal clipping path.')
                continue
            if key not in ATTRS or any(word in value.lower() for word in ('url(', 'javascript:', 'file:')):
                raise ValueError('The SVG contains an unsafe attribute or resource.')
            if key == 'href':
                if not element.tag.endswith('}image') or not re.fullmatch(
                        r'data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=]+', value):
                    raise ValueError('Images must be embedded PNG or JPEG data.')
                try:
                    data = base64.b64decode(value.partition(',')[2], validate=True)
                except ValueError as failure:
                    raise ValueError('The embedded image cannot be decoded.') from failure
                if not (data.startswith(b'\x89PNG\r\n\x1a\n') if value.startswith('data:image/png;')
                        else data.startswith(b'\xff\xd8\xff')):
                    raise ValueError('The image bytes do not match their declared type.')
                image_size(data, 'image/png' if value.startswith('data:image/png;') else 'image/jpeg')
    ET.register_namespace('', SVG)
    return ET.tostring(root, encoding='unicode')


def dimensions(preset: str) -> dict:
    if preset == 'a4':
        return {'width_px': 2480, 'height_px': 3508, 'width_pt': 210 * 72 / 25.4,
                'height_pt': 297 * 72 / 25.4}
    if preset == 'letter':
        return {'width_px': 2550, 'height_px': 3300, 'width_pt': 612, 'height_pt': 792}
    if preset == 'digital':
        return {'width_px': 1080, 'height_px': 1350, 'width_pt': 810, 'height_pt': 1012.5}
    raise ValueError('Choose A4, US Letter, or digital portrait.')


def document(svg: str, preset: str, fonts: list[str]) -> str:
    d = dimensions(preset)
    svg = safe_svg(svg)
    if not fonts or len(fonts) > 16 or any(not isinstance(f, str) or not re.fullmatch(
            r'[A-Za-z0-9][A-Za-z0-9 ._-]{0,100}', f) for f in fonts):
        raise ValueError('Name the actual local fonts the page requires.')
    used = {e.get('font-family') for e in ET.fromstring(svg).iter() if e.get('font-family')}
    if not used.issubset(fonts):
        raise ValueError('Every scene font must be listed for verification.')
    if any(e.tag.endswith('}text') and not e.get('font-family') for e in ET.fromstring(svg).iter()):
        raise ValueError('Every text block must declare its actual local font.')
    # Only this trusted script runs; SVG scripts, styles, links and external images
    # have already been refused. local() verifies actual installed font faces.
    script = """
(async () => {
  const missing = [], invalidAssets = [], overflow = [], boxes = [];
  for (const [index, name] of FONTS.entries()) {
    try { await new FontFace('verified_' + index, 'local("' + name + '")').load(); }
    catch (_) { missing.push(name); }
  }
  await document.fonts.ready;
  const root = document.querySelector('svg');
  const images = [...document.querySelectorAll('#asset-checks img')];
  for (const [index, element] of [...root.querySelectorAll('image')].entries()) {
    const image = images[index];
    try {
      if (!image.complete) await new Promise(resolve => { image.onload = resolve; image.onerror = resolve; });
      if (!image.naturalWidth || !image.naturalHeight) throw Error();
      // DOM images participate in document load. decode() on an unattached Image
      // can remain pending after headless virtual time ends on Apple Silicon.
      const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
      canvas.getContext('2d').drawImage(image, 0, 0, 1, 1);
      canvas.getContext('2d').getImageData(0, 0, 1, 1);
    }
    catch (_) { invalidAssets.push(element.getAttribute('data-id') || element.id || 'unnamed'); }
  }
  for (const element of root.querySelectorAll('[data-box]')) {
    const allowed = element.getAttribute('data-box').split(/\\s+/).map(Number);
    const box = element.getBBox();
    if (allowed.length !== 4 || allowed.some(n => !Number.isFinite(n)) ||
        box.x < allowed[0] - .1 || box.y < allowed[1] - .1 ||
        box.x + box.width > allowed[0] + allowed[2] + .1 ||
        box.y + box.height > allowed[1] + allowed[3] + .1) {
      overflow.push(element.getAttribute('data-id') || element.id || 'unnamed');
    }
    boxes.push({id: element.getAttribute('data-id') || element.id,
      x: box.x, y: box.y, width: box.width, height: box.height});
  }
  const bounds = root.viewBox.baseVal;
  for (const element of root.children) {
    if (!element.getBBox || ['defs', 'title', 'desc'].includes(element.tagName)) continue;
    const box = element.getBBox();
    if (box.x < bounds.x - .1 || box.y < bounds.y - .1 ||
        box.x + box.width > bounds.x + bounds.width + .1 ||
        box.y + box.height > bounds.y + bounds.height + .1) overflow.push('page-bounds');
  }
  document.getElementById('metrics').textContent = JSON.stringify({missing_fonts: missing, invalid_assets: invalidAssets,
    overflow, boxes, complete: true});
})().catch(() => { document.getElementById('metrics').textContent = '{"complete":false}'; });
""".replace('FONTS', json.dumps(fonts))
    staged = ''.join('<img alt="" src="' + html.escape(e.get('href'), quote=True) + '">'
                     for e in ET.fromstring(svg).iter() if e.tag.endswith('}image'))
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src 'self' data:">
<style>@page{{size:{d['width_pt']}pt {d['height_pt']}pt;margin:0}}
html,body{{margin:0;padding:0;overflow:hidden}}svg{{display:block;width:{d['width_px']}px;height:{d['height_px']}px}}
pre{{display:none}}@media print{{svg{{width:{d['width_pt']}pt;height:{d['height_pt']}pt}}}}</style>
</head><body><div id="asset-checks" hidden>{staged}</div>{svg}<pre id="metrics"></pre><script>{script}</script></body></html>'''


def _run(executable: Path, work: Path, arguments: list[str], timeout: int) -> str:
    args = [str(executable), '--headless', '--no-first-run', '--no-default-browser-check',
            '--disable-background-networking', '--disable-component-update', '--disable-sync',
            '--disable-extensions', '--metrics-recording-only', '--hide-scrollbars',
            '--force-device-scale-factor=1', '--host-resolver-rules=MAP * ~NOTFOUND',
            '--user-data-dir=' + str(work / 'profile'), *arguments]
    env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL') if key in os.environ}
    env.update(HOME=str(work / 'home'), TMPDIR=str(work))
    (work / 'home').mkdir(exist_ok=True)
    process = subprocess.Popen(args, cwd=work, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as failure:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise ValueError('The local renderer timed out.') from failure
    if process.returncode != 0:
        raise ValueError('The local renderer could not finish. Check its installed capability.')
    return output.decode('utf-8', errors='replace')


def png_size(path: Path) -> tuple[int, int]:
    with Path(path).open('rb') as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
        raise ValueError('The renderer did not return a PNG.')
    return struct.unpack('>II', header[16:24])


def pdf_pages(path: Path) -> list[tuple[float, float]]:
    """Inspect the renderer's own ordinary PDF objects, not arbitrary input PDFs."""
    data = Path(path).read_bytes()
    if not data.startswith(b'%PDF-'):
        raise ValueError('The renderer did not return a PDF.')
    pages = re.findall(rb'(?s)\b\d+\s+\d+\s+obj\b(.*?)\bendobj\b', data)
    sizes = []
    for page in pages:
        if re.search(rb'/Type\s*/Page\b', page):
            box = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]', page)
            if box is None:
                raise ValueError('The generated PDF page size could not be checked.')
            sizes.append(tuple(float(value) for value in box.groups()))
    if not sizes:
        raise ValueError('The generated PDF page count could not be checked.')
    return sizes


def render(svg: str, *, preset: str, fonts: list[str], executable: Path,
           destination: Path, timeout: int = 30) -> dict:
    """Render into a new folder, publishing no partial result on failure."""
    executable = Path(executable).resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError('Supply an installed executable headless renderer.')
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('The rendering attempt needs a new output folder.')
    parent = destination.parent.resolve(strict=True)
    d, page = dimensions(preset), document(svg, preset, fonts)
    with tempfile.TemporaryDirectory(prefix='.infographic-render-', dir=parent) as name:
        work = Path(name)
        source = work / 'scene.html'
        source.write_text(page, encoding='utf-8')
        uri = source.as_uri()
        output = _run(executable, work, ['--virtual-time-budget=2000', '--dump-dom', uri], timeout)
        match = re.search(r'<pre id="metrics">([^<]*)</pre>', output)
        if match is None or not match[1].strip():
            raise ValueError('The renderer returned no font or layout measurements.')
        metrics = json.loads(html.unescape(match[1]))
        if not metrics.get('complete') or metrics.get('missing_fonts') or metrics.get('invalid_assets') or metrics.get('overflow'):
            raise ValueError('The page has missing fonts, invalid assets, overflow, or incomplete measurements.')
        png, pdf = work / 'page.png', work / 'page.pdf'
        _run(executable, work, [f"--window-size={d['width_px']},{d['height_px']}",
                               '--screenshot=' + str(png), uri], timeout)
        _run(executable, work, ['--no-pdf-header-footer', '--print-to-pdf=' + str(pdf), uri], timeout)
        if png_size(png) != (d['width_px'], d['height_px']):
            raise ValueError('The PNG does not match the selected dimensions.')
        pages = pdf_pages(pdf)
        if len(pages) != 1 or any(abs(actual - expected) > 1 for actual, expected in
                                zip(pages[0], (d['width_pt'], d['height_pt']))):
            raise ValueError('The PDF is not one page at the selected dimensions.')
        ready = work / 'ready'
        ready.mkdir()
        for path in (png, pdf):
            path.replace(ready / path.name)
        (ready / 'page.svg').write_text(safe_svg(svg), encoding='utf-8')
        (ready / 'measurements.json').write_text(json.dumps(metrics, indent=2) + '\n', encoding='utf-8')
        ready.rename(parent / destination.name)
    return {'preset': preset, **d, 'pdf_pages': 1, 'measured_elements': len(metrics['boxes'])}
