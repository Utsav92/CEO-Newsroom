import asyncio, json, sys, httpx
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.database import migrate, Session, Source
from app.ingestion import ingest
from app.config import ADMIN_TOKEN

async def main():
    headers={'Authorization':'Bearer '+ADMIN_TOKEN} if ADMIN_TOKEN else {}
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8788',timeout=180,headers=headers) as client:
        try: live=await client.get('/api/health',timeout=3)
        except httpx.RequestError: live=None
        if live is not None:
            live.raise_for_status()
            session=await client.get('/api/session'); session.raise_for_status()
            result=await client.post('/api/news/refresh',json={},headers={'X-Newsroom-Token':session.json()['token']}); result.raise_for_status()
            print(json.dumps(result.json(),indent=2))
            status=await client.get('/api/sources'); status.raise_for_status()
            print(json.dumps([{'id':s['id'],'status':s['status'],'detail':s['detail']} for s in status.json()],indent=2))
            return
    migrate()
    print(json.dumps(await ingest(),indent=2))
    with Session() as db:
        print(json.dumps([{'id':s.id,'status':s.status,'detail':s.detail} for s in db.query(Source).all()],indent=2))
if __name__ == '__main__': asyncio.run(main())
