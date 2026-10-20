import asyncio, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.database import migrate,Session,Article
from app.rag import index_articles

async def main():
    migrate()
    with Session() as db: ids=[a.id for a in db.query(Article).all()]
    print(json.dumps(await index_articles(ids),indent=2))
if __name__=='__main__': asyncio.run(main())
