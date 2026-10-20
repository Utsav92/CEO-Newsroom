"""Prepare private PostgreSQL DDL and bound parameters for Neon's HTTPS driver."""
import argparse,json,os,sqlite3,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ['VERCEL']='0'
from app.database import Base,AudioCache
from sqlalchemy.schema import CreateTable,CreateIndex
from sqlalchemy.dialects import postgresql


def prepare(verify=False):
    schema='newsroom_migration_check' if verify else 'public'
    snapshot=ROOT/'data'/('before-vercel-https-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.sqlite')
    with sqlite3.connect((ROOT/'data'/'newsroom.db').as_uri()+'?mode=ro',uri=True) as source:
        with sqlite3.connect(snapshot) as backup:source.backup(backup)
    source=sqlite3.connect(snapshot);source.row_factory=sqlite3.Row
    names={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    dataset={table.name:[dict(r) for r in source.execute('SELECT * FROM "'+table.name+'"')] if table.name in names else [] for table in Base.metadata.sorted_tables}
    dataset['login_sessions']=[]
    dataset['security_buckets']=[];dataset['job_leases']=[]
    dataset['schema_versions']=[{'version':i} for i in range(1,7)]
    dataset['audio_cache']=[{'id':p.stem,'data':'\\x'+p.read_bytes().hex()} for p in (ROOT/'data'/'audio').glob('*.mp3') if len(p.stem)==64]
    discarded={}
    for table in Base.metadata.sorted_tables:
        rows=dataset[table.name]
        for fk in table.foreign_keys:
            valid={r[fk.column.name] for r in dataset[fk.column.table.name]}
            invalid=[r for r in rows if r.get(fk.parent.name) is not None and r[fk.parent.name] not in valid]
            if invalid:
                if table.name not in ('article_companies','article_topics','briefing_articles'):
                    raise RuntimeError('Orphaned private records require inspection: '+table.name)
                rows=[r for r in rows if r not in invalid]
                discarded[table.name]=discarded.get(table.name,0)+len(invalid)
        dataset[table.name]=rows
    dialect=postgresql.dialect(paramstyle='numeric_dollar')
    queries=[{'query':'SET LOCAL search_path TO '+schema,'params':[]}]
    counts={}
    for table in Base.metadata.sorted_tables:
        queries.append({'query':str(CreateTable(table).compile(dialect=dialect)),'params':[]})
        for index in table.indexes:queries.append({'query':str(CreateIndex(index).compile(dialect=dialect)),'params':[]})
        rows=dataset[table.name];counts[table.name]=len(rows)
        for start in range(0,len(rows),100):
            statement=table.insert().values(rows[start:start+100])
            compiled=statement.compile(dialect=dialect)
            queries.append({'query':str(compiled),'params':[compiled.params[k] for k in compiled.positiontup]})
        for col in table.primary_key:
            if col.type.python_type is int and col.autoincrement is not False and rows:
                maximum=max(r[col.name] for r in rows)
                queries.append({'query':"SELECT setval(pg_get_serial_sequence($1,$2),$3,true)",
                                'params':[table.name,col.name,maximum]})
    for table,count in counts.items():queries.append({'query':'SELECT COUNT(*) AS count FROM "'+table+'"','params':[]})
    output=ROOT/'output'/'http-migration-plan.json'
    output.write_text(json.dumps({'schema':schema,'verify':verify,'queries':queries,'counts':counts,'discarded_stale_joins':discarded,'backup':snapshot.name}),encoding='utf-8')
    print(json.dumps({'prepared':True,'schema':schema,'counts':counts,'discarded_stale_joins':discarded,'plan_bytes':output.stat().st_size,'backup':snapshot.name}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    prepare(args.verify)
