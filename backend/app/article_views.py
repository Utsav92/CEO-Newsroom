import json
from .personas import BY_COMPANY

def article_json(a):
    companies=json.loads(a.companies)
    return dict(id=a.id,url=a.url,title=a.title,source=a.source,published_at=a.published_at,ingested_at=a.ingested_at,summary=a.summary,excerpt=a.excerpt,why_it_matters=a.why_it_matters,companies=companies,topics=json.loads(a.topics),presenters=[BY_COMPANY[c]['id'] for c in companies if c in BY_COMPANY],image=a.image,classification=a.classification,summary_kind=a.summary_kind,significance=a.rank)
