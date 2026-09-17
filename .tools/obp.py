import json,sys,subprocess,re,html
import urllib.request

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"

def post(url, tok=None, data=b'{}'):
    req=urllib.request.Request(url, data=data, method='POST')
    req.add_header('User-Agent',UA); req.add_header('Content-Type','application/json'); req.add_header('Accept','application/json')
    if tok: req.add_header('Authorization','Bearer '+tok)
    return urllib.request.urlopen(req, timeout=60).read()

def get(url):
    req=urllib.request.Request(url); req.add_header('User-Agent',UA); req.add_header('Accept','application/json')
    return urllib.request.urlopen(req, timeout=60).read()

def strip(h):
    if not h: return ''
    h=re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>',' ',h)
    h=re.sub(r'(?is)<br\s*/?>','\n',h)
    h=re.sub(r'(?is)</(p|div|li|h[1-6]|tr|td|th)>','\n',h)
    t=html.unescape(re.sub(r'(?s)<[^>]+>','',h))
    t=t.replace('\u00a0',' ')
    t=re.sub(r'[ \t]+',' ',t); t=re.sub(r'\n\s*\n+','\n',t)
    return t.strip()

def main(project_id, outprefix, want=None):
    tok=json.loads(get('https://obp.iso.org/auth/token-exchange?token=anonymous-standalone-reader'))['authzData']
    ci=json.loads(post(f'https://obp.iso.org/api/project/{project_id}/chunk-info?lang=en', tok))
    print('chunk-info:', json.dumps(ci))
    dp=json.loads(post(f"https://obp.iso.org/api/standards/{ci['docId']}/data-package?chunkId={ci['id']}", tok))
    open(outprefix+'_obp_datapackage.json','w',encoding='utf-8').write(json.dumps(dp)[:2000000])
    print('standardDoc:', json.dumps(dp['standardDoc'].get('titles')), dp['standardDoc'].get('reference'))
    print('metadata:', json.dumps(dp['standardDoc'].get('metadata'))[:800])
    for ch in dp['chunks']:
        sem=ch.get('semId','')
        if want and sem not in want: continue
        print('='*25, sem, ch.get('displayValue','')[:60], 'access=',ch.get('hasAccess'))
        print(strip(ch.get('content')))
        print()

if __name__=='__main__':
    pid=sys.argv[1]; out=sys.argv[2]
    want=sys.argv[3:] or None
    main(pid,out,want)
