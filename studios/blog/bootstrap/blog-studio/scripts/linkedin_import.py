#!/usr/bin/env python3
"""Read only profile background and article samples from a supplied LinkedIn ZIP."""
import argparse
import csv
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import sys
import zipfile

MAX_SELECTED_BYTES = 25 * 1024 * 1024


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0;self.in_title = False;self.title = [];self.body = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'):self.skip += 1
        if tag == 'title':self.in_title = True
        if tag in ('p','div','section','article','br','h1','h2','h3','li'):self.body.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script','style') and self.skip:self.skip -= 1
        if tag == 'title':self.in_title = False
        if tag in ('p','div','section','article','h1','h2','h3','li'):self.body.append('\n')

    def handle_data(self, data):
        if self.skip:return
        if self.in_title:self.title.append(data)
        else:self.body.append(data)

    def result(self):
        lines=[re.sub(r'\s+',' ',line).strip() for line in ''.join(self.body).splitlines()]
        lines=[line for line in lines if line and not re.match(r'^(Created on|Published on)\b',line)]
        return ''.join(self.title).strip(),'\n\n'.join(lines)


def parse(data, nested=False):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files=[info for info in archive.infolist() if not info.is_dir()]
        if len(files)==1 and files[0].filename.lower().endswith('.zip'):
            if nested:raise ValueError('Nested export exceeds supported depth; upload the inner export.')
            if files[0].file_size>MAX_SELECTED_BYTES:raise ValueError('Inner export exceeds 25 MB; upload selected material instead.')
            return parse(archive.read(files[0]),nested=True)
        selected=[info for info in files if info.filename.lower().endswith('profile.csv') or
                  ('articles/' in info.filename.lower() and info.filename.lower().endswith(('.html','.htm')))]
        if sum(info.file_size for info in selected)>MAX_SELECTED_BYTES:
            raise ValueError('Selected profile/articles exceed 25 MB; provide a smaller selection.')
        result={'headline':'','summary':'','articles':[],'limitations':[],
                'note':'Profile fields are author background; classify authored articles separately as voice samples.'}
        profiles=[info for info in selected if info.filename.lower().endswith('profile.csv')]
        if profiles:
            rows=list(csv.DictReader(io.StringIO(archive.read(profiles[0]).decode('utf-8-sig'))))
            if rows:
                result['headline']=(rows[0].get('Headline') or '').strip()
                result['summary']=(rows[0].get('Summary') or '').strip()
        for info in selected:
            if info.filename.lower().endswith(('.html','.htm')):
                parser=ArticleText();parser.feed(archive.read(info).decode('utf-8',errors='replace'))
                title,text=parser.result()
                if text.strip():result['articles'].append({'title':title or Path(info.filename).stem,'text':text,'origin':info.filename})
        if not result['headline'] and not result['summary'] and not result['articles']:
            raise ValueError('No readable Profile.csv background or Articles HTML found. Supply profile text or authored samples.')
        if not result['articles']:result['limitations'].append('No article samples were present; background alone is not a learned writing voice.')
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--file',required=True);p.add_argument('--out')
    args=p.parse_args()
    try:
        result=parse(Path(args.file).read_bytes())
        body=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
        if args.out:
            out=Path(args.out)
            if out.exists():raise ValueError('Output already exists; choose a new path to preserve it.')
            out.parent.mkdir(parents=True,exist_ok=True)
            with out.open('x',encoding='utf-8') as stream:stream.write(body)
            print(str(out.resolve()))
        else:print(body,end='')
    except (OSError,ValueError,zipfile.BadZipFile,RuntimeError,csv.Error) as exc:
        print(f'Blog Studio LinkedIn import: {exc}',file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
