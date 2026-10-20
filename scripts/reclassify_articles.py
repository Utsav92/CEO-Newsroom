"""Re-evaluate existing routing after classification improvements."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.database import Session,Article,ArticleCompany,migrate
from app.ai import embed,classify,PROTOTYPES
from app.ingestion import REGISTRY

async def main():
    migrate()
    prototypes=await embed(PROTOTYPES)
    official={s['name']:s.get('company') for s in REGISTRY}
    changed=0
    with Session.begin() as db:
        for a in db.query(Article).all():
            companies,topics=classify(a.title+' '+a.excerpt,official.get(a.source),json.loads(a.embedding),prototypes,title=a.title)
            if companies!=json.loads(a.companies): changed+=1
            a.companies=json.dumps(companies);a.topics=json.dumps(topics);a.classification='headline entities + semantic + official source'
            db.query(ArticleCompany).filter_by(article_id=a.id).delete()
            for c in companies: db.add(ArticleCompany(article_id=a.id,company=c))
    print(json.dumps({'articles_reclassified':changed}))
if __name__=='__main__': asyncio.run(main())
