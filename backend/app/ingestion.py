import asyncio, calendar, hashlib, json, re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.robotparser import RobotFileParser
from email.utils import parsedate_to_datetime
import feedparser, httpx,ipaddress
from bs4 import BeautifulSoup
from .database import Session, Article, Source, IngestionJob, ArticleCompany, ArticleTopic, now_iso
from .ai import embed, classify, summarize, PROTOTYPES, AIUnavailable
from .config import OPENAI_KEY

REGISTRY = [
    dict(id='openai',name='OpenAI News',url='https://openai.com/news/rss.xml',kind='rss',company='OpenAI'),
    dict(id='meta',name='Meta Newsroom',url='https://about.fb.com/news/feed/',kind='rss',company='Meta'),
    dict(id='apple',name='Apple Newsroom',url='https://www.apple.com/newsroom/rss-feed.rss',kind='rss',company='Apple'),
    dict(id='google',name='Google Blog',url='https://blog.google/rss/',kind='rss',company='Google'),
    dict(id='anthropic',name='Anthropic News',url='https://www.anthropic.com/news',kind='html',company='Anthropic',prefix='/news/'),
    dict(id='perplexity',name='Perplexity Blog',url='https://www.perplexity.ai/hub/blog',kind='html',company='Perplexity',prefix='/hub/blog/'),
    dict(id='netflix',name='Netflix TechBlog',url='https://netflixtechblog.com/feed',kind='rss',company='Netflix'),
    dict(id='nvidia',name='NVIDIA Blog',url='https://blogs.nvidia.com/feed/',kind='rss',company='NVIDIA',note='Personal, non-commercial RSS use.'),
    dict(id='nvidia-developer',name='NVIDIA Developer',url='https://developer.nvidia.com/blog/feed/',kind='rss',company='NVIDIA'),
    dict(id='techcrunch',name='TechCrunch',url='https://techcrunch.com/feed/',kind='rss'),
    dict(id='verge',name='The Verge',url='https://www.theverge.com/rss/index.xml',kind='rss'),
    dict(id='tldr',name='TLDR',url='https://tldr.tech/archive',kind='tldr'),
    dict(id='apple-research',name='Apple ML Research',url='https://machinelearning.apple.com/rss.xml',kind='rss',company='Apple'),
    dict(id='google-research',name='Google Research',url='https://research.google/blog/rss/',kind='rss',company='Google'),
]
lock = asyncio.Lock()
UA = 'CEONewsroom/1.0 (+local personal news reader)'

async def source_request_guard(request):
    """Apply the source allowlist again to every HTTP redirect and metadata request."""
    p=urlsplit(str(request.url));host=p.hostname or ''
    roots={urlsplit(s['url']).hostname.removeprefix('www.') for s in REGISTRY}
    roots.update({'nvidia.com','apple.com','openai.com','medium.com'})
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or not any(host==root or host.endswith('.'+root) for root in roots):
        raise httpx.RequestError('Source request blocked by the outbound allowlist.',request=request)
    try:
        if not ipaddress.ip_address(host).is_global:raise httpx.RequestError('Private source addresses are blocked.',request=request)
    except ValueError:pass

def canonical_url(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.netloc: return ''
    query=urlencode([(k,v) for k,v in parse_qsl(p.query) if not k.startswith('utm_') and k not in ['fbclid','gclid']])
    return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip('/'),query,''))

def clean(text, limit=600):
    return re.sub(r'\s+',' ',BeautifulSoup(text or '', 'html.parser').get_text(' ',strip=True)).strip()[:limit]

def iso_date(value):
    if not value: return None
    try:
        if isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            day=datetime.fromisoformat(value).date()
            return value if day<=datetime.now(timezone.utc).date()+timedelta(days=1) else None
        if isinstance(value,tuple): d=datetime.fromtimestamp(calendar.timegm(value),timezone.utc)
        else:
            try: d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
            except ValueError: d=parsedate_to_datetime(value)
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        d=d.astimezone(timezone.utc)
        if d > datetime.now(timezone.utc)+timedelta(days=1): return None
        return d.isoformat()
    except (ValueError,TypeError,OverflowError): return None

def parse_feed(body,source):
    feed=feedparser.parse(body)
    if not feed.entries: raise ValueError('Endpoint returned no RSS/Atom entries')
    result=[]
    for e in feed.entries[:12]:
        url=canonical_url(e.get('link',''))
        title=clean(e.get('title',''),240)
        if not title or not url: continue
        summary=e.get('summary','')
        soup=BeautifulSoup(summary,'html.parser')
        image=(e.get('media_thumbnail') or e.get('media_content') or [{}])[0].get('url')
        if not image and soup.img: image=soup.img.get('src')
        result.append(dict(url=url,title=title,published_at=iso_date(e.get('published_parsed')),excerpt=clean(summary),image=image,source=source['name']))
    return result

async def allowed(client,url):
    p=urlsplit(url); robots_url=f'{p.scheme}://{p.netloc}/robots.txt'
    cache=getattr(client,'_newsroom_robots',{})
    if robots_url in cache:
        result=cache[robots_url]
        return result if isinstance(result,bool) else result.can_fetch(UA,url)
    r=await client.get(robots_url)
    if r.status_code==404: result=True
    elif r.status_code!=200: result=False
    else:
        result=RobotFileParser(); result.parse(r.text.splitlines())
    cache[robots_url]=result; client._newsroom_robots=cache
    if isinstance(result,bool): return result
    robot=result
    return robot.can_fetch(UA,url)

def html_metadata(body,url,source):
    soup=BeautifulSoup(body,'html.parser')
    def meta(name):
        tag=soup.find('meta',attrs={'property':name}) or soup.find('meta',attrs={'name':name})
        return tag.get('content') if tag else None
    title=meta('og:title') or (soup.h1.get_text(' ',strip=True) if soup.h1 else '')
    published=meta('article:published_time')
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            queue=[json.loads(script.string or script.get_text())]
            while queue:
                node=queue.pop()
                if isinstance(node,list): queue.extend(node)
                elif isinstance(node,dict):
                    published=published or node.get('datePublished')
                    queue.extend(v for v in node.values() if isinstance(v,(dict,list)))
        except ValueError: pass
    if not published:
        time=soup.find('time')
        published=time.get('datetime') if time else None
    return dict(url=canonical_url(url),title=clean(title,240),published_at=iso_date(published),excerpt=clean(meta('description') or meta('og:description') or '',550),image=meta('og:image'),source=source['name'])

async def fetch_source(client,source):
    if source['kind'] in ('html','tldr') and not await allowed(client,source['url']):
        raise ValueError('Public page access disallowed or robots.txt unavailable; not scraped')
    r=await client.get(source['url']); r.raise_for_status()
    if source['kind']=='rss':
        rows=parse_feed(r.content,source)
        # Apple Atom supplies an updated timestamp, not a publication timestamp.
        # Recover datePublished from the public original rather than relabeling it.
        semaphore=asyncio.Semaphore(3)
        async def recover_date(row):
            if row['published_at'] or urlsplit(row['url']).netloc!=urlsplit(source['url']).netloc: return
            async with semaphore:
                try:
                    if not await allowed(client,row['url']): return
                    page=await client.get(row['url'])
                    if page.status_code==200: row['published_at']=html_metadata(page.text,row['url'],source)['published_at']
                except (httpx.HTTPError,ValueError): pass
        await asyncio.gather(*(recover_date(row) for row in rows))
        return rows
    soup=BeautifulSoup(r.text,'html.parser')
    links=[]
    for a in soup.select('a[href]'):
        url=urljoin(source['url'],a['href'])
        path=urlsplit(url).path
        valid=(source['kind']=='html' and path.startswith(source['prefix']) and len(path)>len(source['prefix'])) or (source['kind']=='tldr' and re.search(r'/tech/\d{4}-\d{2}-\d{2}$',path))
        if '/category/' in path: continue
        if valid and url not in links and urlsplit(url).netloc==urlsplit(source['url']).netloc: links.append(url)
    results=[]
    for url in links[:4 if source['kind']=='html' else 2]:
        if not await allowed(client,url): continue
        page=await client.get(url)
        if page.status_code!=200: continue
        if source['kind']=='html':
            data=html_metadata(page.text,url,source)
            if data['title']: results.append(data)
        else:
            # Retain only newsletter headline, original link, date and a short
            # supplied excerpt; never archive the full newsletter/article.
            news=BeautifulSoup(page.text,'html.parser')
            published=iso_date(urlsplit(url).path.split('/')[-1])
            for heading in news.select('h3')[:12]:
                a=heading.find('a') or heading.find_parent('a')
                if not a: continue
                link=canonical_url(urljoin(url,a.get('href','')))
                if not link: continue
                results.append(dict(url=link,title=clean(heading.get_text(),240),published_at=published,excerpt='',image=None,source=source['name']))
    if not results: raise ValueError('No dated public announcement metadata found; no content fabricated')
    return results

async def ingest():
    from .config import SERVERLESS
    if SERVERLESS:
        from .serverless import run_exclusive
        return await run_exclusive('news-ingestion',_ingest)
    return await _ingest()

async def _ingest():
    if lock.locked(): return {'status':'already running','added':0}
    async with lock:
        with Session.begin() as db:
            job=IngestionJob(); db.add(job); db.flush(); job_id=job.id
        results=[]
        async with httpx.AsyncClient(timeout=18,follow_redirects=True,headers={'User-Agent':UA},event_hooks={'request':[source_request_guard]}) as client:
            semaphore=asyncio.Semaphore(5)
            async def one(source):
                async with semaphore:
                    try:
                        rows=await fetch_source(client,source)
                        return source,rows,'available',f'{len(rows)} entries fetched'
                    except Exception as exc:
                        detail=f'HTTP {exc.response.status_code}' if isinstance(exc,httpx.HTTPStatusError) else str(exc)[:180] or type(exc).__name__
                        return source,[],'unavailable',detail
            results=await asyncio.gather(*(one(s) for s in REGISTRY))
        pending=[]
        with Session.begin() as db:
            existing_urls={a.url for a in db.query(Article).all()}
            existing_titles={re.sub(r'\W+','',a.title.lower()) for a in db.query(Article).all()}
            for source,rows,status,detail in results:
                record=db.get(Source,source['id'])
                if record is None: record=Source(id=source['id'],config=json.dumps(source)); db.add(record)
                record.status=status; record.checked_at=now_iso(); record.detail=detail
                for row in rows:
                    fingerprint=re.sub(r'\W+','',row['title'].lower())
                    if row['url'] in existing_urls:
                        existing=db.query(Article).filter_by(url=row['url']).first()
                        if existing and existing.source==row['source']: existing.published_at=row['published_at']
                        continue
                    if fingerprint in existing_titles: continue
                    existing_urls.add(row['url']); existing_titles.add(fingerprint)
                    row['official']=source.get('company'); pending.append(row)
        vectors=[]; prototypes=[]; ai_error=None
        if pending and OPENAI_KEY:
            try:
                all_vectors=await embed(PROTOTYPES+[row['title']+' '+row['excerpt'] for row in pending])
                prototypes=all_vectors[:8]; vectors=all_vectors[8:]
            except Exception as exc: ai_error=str(exc)[:180]
        added=0
        with Session.begin() as db:
            for i,row in enumerate(pending):
                official=row.pop('official'); vector=vectors[i] if vectors else []
                companies,topics=classify(row['title']+' '+row['excerpt'],official,vector,prototypes,title=row['title'])
                id=hashlib.sha256(row['url'].encode()).hexdigest()[:20]
                db.add(Article(id=id,**row,companies=json.dumps(companies),topics=json.dumps(topics),embedding=json.dumps(vector),summary=row['excerpt'] or row['title'],rank=3 if official else 2,classification='entities + semantic' if vector else 'source + entities'))
                db.flush()
                for c in companies: db.add(ArticleCompany(article_id=id,company=c))
                for t in topics: db.add(ArticleTopic(article_id=id,topic=t))
                added+=1
            payload={'status':'complete','added':added,'sources_available':sum(r[2]=='available' for r in results),'sources_total':len(REGISTRY),'ai_error':ai_error}
            job=db.get(IngestionJob,job_id); job.finished_at=now_iso(); job.payload=json.dumps(payload)
        # Grounded summaries for a bounded number of newest items. All other
        # cards explicitly retain source excerpts rather than invented summaries.
        if OPENAI_KEY and not ai_error:
            newest=sorted(pending,key=lambda r:r.get('published_at') or '',reverse=True)[:8]
            async def enrich(row):
                try:
                    output=await summarize({k:row[k] for k in ['title','excerpt','published_at','source']})
                    with Session.begin() as db:
                        a=db.query(Article).filter_by(url=row['url']).first()
                        a.summary=output['summary']; a.why_it_matters=output['why_it_matters']; a.summary_kind='AI summary'
                except Exception: pass
            await asyncio.gather(*(enrich(row) for row in newest))
        if pending:
            from .rag import index_articles
            try:
                await index_articles([hashlib.sha256(row['url'].encode()).hexdigest()[:20] for row in pending],embed_missing=bool(OPENAI_KEY and not ai_error))
            except Exception:
                # Saved text remains searchable; lazy retrieval retries missing vectors.
                pass
        return payload
