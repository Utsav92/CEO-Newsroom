"""Copy a consistent local SQLite snapshot into a fresh provisioned PostgreSQL schema.

Never replaces populated data or copies active login sessions. Connection strings
are loaded from the ignored Vercel env file and never logged.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime,timezone
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-schema',action='store_true')
    args=parser.parse_args()
    settings=dotenv_values(ROOT/'output'/'vercel-production.env')
    url=settings.get('DATABASE_URL_UNPOOLED') or settings.get('DATABASE_URL')
    if not url:raise SystemExit('Pull the connected production database environment first.')
    if url.startswith(('postgres://','postgresql://')):url='postgresql+psycopg://'+url.split('://',1)[1]
    from sqlalchemy import create_engine,select,text,inspect,func
    from sqlalchemy.engine import make_url
    schema='newsroom_migration_check' if args.verify_schema else 'public'
    direct=create_engine(url,connect_args={'connect_timeout':20})
    if args.verify_schema:
        with direct.begin() as connection:
            # The fixed test-only schema is owned by this migration tool.
            exists=connection.execute(text('SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name=:name)'),{'name':schema}).scalar()
            if exists:raise SystemExit('Verification schema already exists; inspect it before retrying.')
            connection.execute(text('CREATE SCHEMA newsroom_migration_check'))
        url=make_url(url).update_query_dict({'options':'-c search_path=newsroom_migration_check'}).render_as_string(hide_password=False)
    os.environ.update({'DATABASE_URL':url,'NEWSROOM_DATA_DIR':str(ROOT/'output'/'migration-scratch'),'VERCEL':'0'})
    from app import database
    from app.database import Base,engine,Session,Account,Article,AudioCache
    Base.metadata.create_all(engine)
    print('Target schema ready: '+schema,flush=True)
    with Session() as db:
        if db.query(Account).count() or db.query(Article).count():
            raise SystemExit('Target is populated. Refusing to replace existing cloud data.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snapshot=ROOT/'data'/('before-vercel-'+stamp+'.sqlite')
    with sqlite3.connect((ROOT/'data'/'newsroom.db').as_uri()+'?mode=ro',uri=True) as source:
        with sqlite3.connect(snapshot) as backup:source.backup(backup)
    source=sqlite3.connect(snapshot);source.row_factory=sqlite3.Row
    tables={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    counts={}
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in tables or table.name in ('login_sessions','security_buckets','job_leases'):continue
            rows=[dict(r) for r in source.execute('SELECT * FROM "'+table.name+'"')]
            if rows:connection.execute(table.insert(),rows)
            counts[table.name]=len(rows)
        for table in Base.metadata.sorted_tables:
            for column in table.primary_key:
                if column.type.python_type is int and column.autoincrement is not False:
                    sequence=connection.execute(text('SELECT pg_get_serial_sequence(:table,:column)'),{'table':table.name,'column':column.name}).scalar()
                    if sequence:
                        maximum=connection.execute(select(func.max(column))).scalar() or 0
                        connection.execute(text('SELECT setval(CAST(:sequence AS regclass),:value,:used)'),{'sequence':sequence,'value':max(maximum,1),'used':maximum>0})
        for path in (ROOT/'data'/'audio').glob('*.mp3'):
            if len(path.stem)==64:connection.execute(AudioCache.__table__.insert().values(id=path.stem,data=path.read_bytes()))
    source.close()
    print('Snapshot copied; checking additive migrations.',flush=True)
    database.migrate()
    with engine.connect() as connection:
        for name,count in counts.items():
            actual=connection.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar()
            if name!='schema_versions' and actual!=count:raise RuntimeError('Migration row-count mismatch: '+name)
    report={'schema':schema,'counts':counts,'backup':snapshot.name,'verified':True,'active_sessions_copied':False}
    (ROOT/'output'/('vercel-migration-check.json' if args.verify_schema else 'vercel-migration.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    if args.verify_schema:
        engine.dispose()
        with direct.begin() as connection:connection.execute(text('DROP SCHEMA newsroom_migration_check CASCADE'))
    direct.dispose()


if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Database errors can contain SQL parameters or connection details.
        print('Migration stopped safely: '+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1) from None
