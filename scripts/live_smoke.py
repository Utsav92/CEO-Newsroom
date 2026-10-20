"""Bounded live verification. Does not print secrets or provider request bodies."""
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
def main():
    report={}
    with httpx.Client(base_url='http://127.0.0.1:8788',timeout=100) as c:
        token=c.get('/api/session').json()['token']; headers={'X-Newsroom-Token':token}
        health=c.get('/api/health').json(); report['health']=health
        ceos=c.get('/api/ceos').json(); report['presenters']=len(ceos)
        report['companies']={p['company']:len(c.get('/api/news/company/'+p['company']).json()['articles']) for p in ceos}
        result=c.post('/api/chat',json={'question':'Compare the latest OpenAI and Anthropic announcements in the collected reporting.','period':'month'},headers=headers)
        report['chat_status']=result.status_code
        if result.status_code==200:
            answer=result.json(); report['chat']={'presenters':[m['presenter'] for m in answer['messages']],'citations':sum(len(m['citations']) for m in answer['messages']),'answer':answer['messages']}
            audio=c.post('/api/audio',json={'text':'This is an AI-generated CEO Newsroom voice test. Reporting comes with original sources.','presenter':'sam_altman'},headers=headers)
            report['audio_status']=audio.status_code
            if audio.status_code==200:
                file=c.get(audio.json()['url']); report['audio']={'bytes':len(file.content),'status':file.status_code,'voice':audio.json()['voice']}
        report['youtube_missing_key_status']=c.get('/api/youtube/search').status_code
        report['briefing_stories']=len(c.get('/api/briefings/today').json()['articles'])
    (ROOT/'output').mkdir(exist_ok=True)
    (ROOT/'output'/'live-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['chat','health']},indent=2))
if __name__=='__main__': main()
