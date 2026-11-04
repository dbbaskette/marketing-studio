"""What the stand-in Harness Brand answers. Small, made-up and deterministic.

Environment for tests:
  STAND_IN_NAME          the version line's name (default Harness Brand), to play another skill
  STAND_IN_NO_PREVIEWS   set: pack previews fails as Harness Brand does without LibreOffice
  STAND_IN_PROBLEM       a problem pack check reports for every brand pack
  STAND_IN_CALLS         a file each call's arguments are appended to, one JSON line each
"""
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 24
JUDGEMENT = ('relationship', 'contentRange', 'components', 'searchTerms', 'delivery',
             'searchable', 'notes')


def fail(message, code=1):
    print(message, file=sys.stderr)
    raise SystemExit(code)


def say(value):
    print(json.dumps(value, indent=2))


def option(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def positionals(args):
    found, skip = [], False
    for arg in args:
        if skip:
            skip = False
        elif arg.startswith('--'):
            skip = arg not in ('--json', '--replace')
        else:
            found.append(arg)
    return found


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def tokens(args):
    source, into = Path(positionals(args)[0]), Path(option(args, '--into'))
    if source.suffix == '.zip':
        with zipfile.ZipFile(source) as opened:
            name = next((n for n in opened.namelist() if n.endswith('tokens.json')), None)
            if name is None:
                fail(f'{source.name}: it has no tokens.json.')
            given = json.loads(opened.read(name))
    else:
        given = read(source) or fail(f'{source.name} is not a tokens.json.')
    made = {'schema': 1, 'name': given.get('name', 'Example Co'), 'themes': ['light', 'dark'],
            'colors': given.get('colors') or [], 'type': given.get('type') or {'styles': []}}
    write(into / 'tokens.json', made)
    say({'tokens': str(into / 'tokens.json'), 'colors': len(made['colors']),
         'dark': sum(1 for c in made['colors'] if c.get('dark')), 'styles': len(made['type'].get('styles') or [])})


def measure(args):
    template, variant, into = Path(positionals(args)[0]), option(args, '--variant'), Path(option(args, '--into'))
    (into / 'templates').mkdir(parents=True, exist_ok=True)
    shutil.copy(template, into / 'templates' / f'{variant}.pptx')
    layouts = read(into / 'layouts.json') or {'schema': 1, 'variants': {}}
    before = {l['id']: l for l in (layouts['variants'].get(variant) or {}).get('layouts') or []}
    made = []
    for number, name in enumerate(('Title Only', 'Section'), 1):
        ident = f'{variant}-layout-{number:03}'
        layout = {'id': ident, 'name': name, 'used': True, 'renderPage': number,
                  'placeholders': [{'id': '2', 'type': 'title', 'bounds': [48, 36, 864, 60], 'size': 28}]}
        layout.update({k: v for k, v in before.get(ident, {}).items() if k in JUDGEMENT})
        made.append(layout)
    layouts['variants'][variant] = {'template': f'templates/{variant}.pptx', 'canvas': {'width': 960, 'height': 540},
                                    'layouts': made, 'slides': [{'slide': 1, 'hidden': False}]}
    write(into / 'layouts.json', layouts)
    say({'layouts': str(into / 'layouts.json'), 'variant': variant, 'measured': 2, 'used': 2})


def previews(args):
    if os.environ.get('STAND_IN_NO_PREVIEWS'):
        fail('Previews need LibreOffice (soffice) and Poppler (pdftoppm). Install them, or give --soffice and --pdftoppm.')
    pack, variant = Path(positionals(args)[0]), option(args, '--variant')
    layouts = read(pack / 'layouts.json')
    for layout in layouts['variants'][variant]['layouts']:
        path = pack / 'previews' / variant / f"{layout['id']}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG)
        layout['preview'] = f"previews/{variant}/{layout['id']}.png"
    write(pack / 'layouts.json', layouts)
    say({'previews': str(pack / 'previews' / variant), 'drawn': 2, 'without': 0})


def scaffold(args):
    pack = Path(positionals(args)[0])
    if not (pack / 'tokens.json').is_file():
        fail(f'{pack} has no tokens.json. Make it first with pack tokens.')
    layouts = read(pack / 'layouts.json') or {'variants': {}}
    icons = [i for i in (option(args, '--icons') or '').split(',') if i]
    variants = {v: {'theme': 'dark' if v == 'dark' else 'light',
                    'colors': {'canvasPrimary': 'white', 'inkPrimary': 'black', 'headingPrimary': 'blue'},
                    'slides': {'template': f'templates/{v}.pptx', 'layout': 'Title Only'}}
                for v in layouts['variants']} or {'light': {'theme': 'light', 'colors': {'canvasPrimary': 'white'}}}
    draft = ['Check every colour role against the brand book.', 'Put the logos in assets/ and write guide.md.']
    write(pack / 'brand.json', {'schema': 1, 'id': option(args, '--id'), 'name': option(args, '--name'),
                                'aliases': [option(args, '--id')], 'defaultVariant': next(iter(variants)),
                                'fonts': {'sans': 'Arial'}, 'variants': variants,
                                'icons': [{'library': i, 'default': n == 0} for n, i in enumerate(icons)],
                                'logos': {'onLight': 'assets/logo.svg', 'onDark': 'assets/logo.svg'},
                                'draft': draft})
    (pack / 'guide.md').write_text('## Brand rules\n\nReview: write the rules.\n')
    written = ['brand.json', 'guide.md']
    if layouts['variants']:
        write(pack / 'directions.json', {'schema': 1, 'house': [], 'variants': {}})
        write(pack / 'audit.json', {'schema': 1, 'minTextPt': 18})
        written += ['directions.json', 'audit.json']
    say({'pack': str(pack), 'written': written, 'draft': draft})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def files(folder, skip=()):
    folder = Path(folder)
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob('*')
                  if p.is_file() and not p.name.startswith('.') and p.relative_to(folder).parts[0] not in skip
                  and p.relative_to(folder).as_posix() != 'brand.json')


def problems(pack, hashes=True):
    pack = Path(pack)
    brand = read(pack / 'brand.json')
    if not isinstance(brand, dict):
        return ['brand.json cannot be read.']
    found = []
    if 'draft' in brand:
        found.append('brand.json is still a draft: ' + ' '.join(brand['draft']))
    if pack.name == 'pack' and brand.get('id') != pack.parent.name:
        found.append(f"brand.json says its id is {brand.get('id')}, but its folder is {pack.parent.name}.")
    guide = (pack / 'guide.md').read_text() if (pack / 'guide.md').is_file() else ''
    if not guide or 'Review:' in guide:
        found.append('guide.md still has lines that start with Review:.')
    for variant, measured in ((read(pack / 'layouts.json') or {}).get('variants') or {}).items():
        for layout in measured['layouts']:
            if 'relationship' not in layout:
                found.append(f"Layout {layout['name']} of {variant} has no relationship.")
    for logo in (brand.get('logos') or {}).values():
        if not (pack / logo).is_file():
            found.append(f'The logo {logo} is not in the pack.')
    for library in brand.get('icons') or []:
        if not (pack.parent.parent / 'icon-libraries' / library['library'] / 'library.zip').is_file():
            found.append(f"Icon library {library['library']} is not in brands/icon-libraries/.")
    if os.environ.get('STAND_IN_PROBLEM'):
        found.append(os.environ['STAND_IN_PROBLEM'])
    if hashes and 'files' in brand:
        for name, digest in brand['files'].items():
            if not (pack / name).is_file() or sha(pack / name) != digest:
                found.append(f'{name} changed since the pack was sealed. Seal the pack again.')
        for name, digest in brand.get('sources', {}).items():
            source = pack.parent / 'sources' / name
            if not source.is_file() or sha(source) != digest:
                found.append(f'The source {name} changed since the pack was sealed. Seal the pack again.')
    return found


def check(args):
    folder = Path(positionals(args)[0])
    if (folder / 'library.zip').is_file():
        try:
            with zipfile.ZipFile(folder / 'library.zip') as opened:
                json.loads(opened.read('library.json'))
            listed = []
        except (KeyError, ValueError, zipfile.BadZipFile):
            listed = ['library.zip is not an icon library.']
    elif (folder / 'brand.json').is_file():
        listed = problems(folder)
    else:
        fail(f'{folder} is neither an icon library nor a brand pack.')
    say({'ok': not listed, 'problems': listed})
    raise SystemExit(1 if listed else 0)


def seal(args):
    pack = Path(positionals(args)[0])
    left = problems(pack, hashes=False)
    if left:
        fail('The pack does not pass, so it was not sealed:\n' + '\n'.join(left))
    brand = read(pack / 'brand.json')
    brand['files'] = {name: sha(pack / name) for name in files(pack, skip=('previews',))}
    brand['sources'] = {name: sha(pack.parent / 'sources' / name) for name in files(pack.parent / 'sources')}
    brand['brandSha256'] = 'f' * 64
    write(pack / 'brand.json', brand)
    say({'brand': str(pack / 'brand.json'), 'files': len(brand['files']), 'sources': len(brand['sources'])})


def icons(args):
    into = Path(option(args, '--into'))
    drawings, skipped = [], []
    for place in map(Path, positionals(args)):
        found = []
        if place.suffix == '.zip':
            with zipfile.ZipFile(place) as opened:
                found = [(n, opened.read(n).decode()) for n in opened.namelist() if n.endswith('.svg')]
        elif place.suffix == '.svg':
            found = [(place.name, place.read_text())]
        elif place.suffix == '.json':
            found = [(f"{place.name}#{n}", '<svg/>') for n, _ in enumerate((read(place) or {}).get('icons') or [])]
        for name, text in found:
            if '<text' in text:
                skipped.append({'source': place.name, 'file': name, 'reason': 'it holds text, which is not a glyph'})
            else:
                drawings.append(name)
    if not drawings:
        fail('No icons were found in those sources. Nothing was written.')
    into.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(into / 'library.zip', 'w') as made:
        made.writestr('library.json', json.dumps({'schema': 1, 'id': option(args, '--library'),
                                                  'name': option(args, '--name'), 'kind': option(args, '--kind')}))
        made.writestr('icons.json', json.dumps({'schema': 1, 'icons': [{'slug': n} for n in drawings]}))
    (into / 'contact-sheet.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
    say({'library': str(into / 'library.zip'), 'kind': option(args, '--kind'), 'icons': len(drawings),
         'sources': [], 'skipped': skipped, 'contactSheet': str(into / 'contact-sheet.svg')})


def brands(args):
    data = os.environ.get('HARNESS_BRAND_DATA')
    listed = []
    for pack in sorted(Path(data).glob('*/pack')) if data else []:
        brand = read(pack / 'brand.json')
        if brand and not problems(pack):
            listed.append({'brand': brand['id'], 'name': brand['name'], 'variants': list(brand['variants'])})
    if not listed:
        fail(f'{data} holds no brand pack that passes pack check.')
    print(json.dumps(listed))


def main(args):
    if os.environ.get('STAND_IN_CALLS'):
        with open(os.environ['STAND_IN_CALLS'], 'a') as calls:
            calls.write(json.dumps(args) + '\n')
    if args[:1] == ['version']:
        print(os.environ.get('STAND_IN_NAME', 'Harness Brand') + ' 1.0.0')
        return
    if args[:1] == ['brands']:
        return brands(args[1:])
    if args[:1] == ['pack'] and len(args) > 1:
        commands = {'tokens': tokens, 'measure': measure, 'previews': previews, 'scaffold': scaffold,
                    'check': check, 'seal': seal, 'icons': icons}
        if args[1] in commands:
            return commands[args[1]](args[2:])
    fail(f'{" ".join(args)} is not a stand-in command.', 2)


if __name__ == '__main__':
    main(sys.argv[1:])
