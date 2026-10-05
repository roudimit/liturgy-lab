"""Render static report pages from Markdown, with shared typography and navigation."""
from pathlib import Path
import hashlib
import html
import re
import shutil
from markdown_it import MarkdownIt

PAGES=[('FINDINGS','Findings'),('RESULTS','Detailed results'),('HELP','Help')]

def build_report_pages(project: Path, site: Path):
    reports=site/'reports'
    reports.mkdir(exist_ok=True)
    stylesheet=project/'share-template/site/assets/report.css'
    shutil.copy2(stylesheet,site/'assets/report.css')
    revision=hashlib.sha256(stylesheet.read_bytes()).hexdigest()[:12]
    for stem,label in PAGES:
        source=(project/f'{stem}.md').read_text()
        shutil.copy2(project/f'{stem}.md',reports/f'{stem}.md')
        md=MarkdownIt('commonmark',{'html':False,'linkify':False}).enable('table')
        tokens=md.parse(source)
        contents=[]
        seen={}
        for i,token in enumerate(tokens):
            if token.type=='heading_open':
                title=tokens[i+1].content
                slug=re.sub(r'[^a-z0-9]+','-',title.casefold()).strip('-') or 'section'
                seen[slug]=seen.get(slug,0)+1
                identifier=slug if seen[slug]==1 else f'{slug}-{seen[slug]}'
                token.attrSet('id',identifier)
                if token.tag=='h2':
                    contents.append(f'<li><a href="#{identifier}">{html.escape(title)}</a></li>')
        md.renderer.rules['table_open']=lambda *args:'<div class="table-scroll"><table>\n'
        md.renderer.rules['table_close']=lambda *args:'</table></div>\n'
        body=md.renderer.render(tokens,md.options,{})
        links=['<a href="../">Viewer</a>']
        for other,title in PAGES:
            current=' aria-current="page"' if other==stem else ''
            links.append(f'<a href="{other}.html"{current}>{title}</a>')
        rendered=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{label} · Liturgy Lab</title><link rel="stylesheet" href="../assets/report.css?v={revision}"></head>
<body><header><div class="topbar"><a class="brand" href="../">Liturgy<span>Lab</span></a>
<nav class="nav" aria-label="Main navigation">{''.join(links)}</nav></div></header>
<main class="layout"><aside><details class="contents" open><summary>On this page</summary><ul>{''.join(contents)}</ul></details></aside>
<article><p class="eyebrow">Liturgy Lab · Local speech experiment</p>{body}
<footer class="document-footer"><a href="../">← Back to the viewer</a><a href="{stem}.md" download>Download Markdown ↓</a></footer></article></main></body></html>'''
        (reports/f'{stem}.html').write_text(rendered)
    index=site/'index.html'
    text=index.read_text().replace('reports/COLLABORATOR-SUMMARY.txt','reports/FINDINGS.html').replace('href="START-HERE.txt">Help','href="reports/HELP.html">Help')
    index.write_text(text)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',type=Path)
    parser.add_argument('site',type=Path)
    args=parser.parse_args()
    build_report_pages(args.project,args.site)
