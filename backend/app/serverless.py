"""Durable coordination and small private narration objects for Vercel Functions."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from fastapi import HTTPException
from .database import engine, Session, AudioCache, now_iso


def shared_rate_limit(key, limit, seconds):
    bucket = hashlib.sha256(repr(key).encode()).hexdigest()
    lock_id = int.from_bytes(bytes.fromhex(bucket[:16]), 'big', signed=True)
    with engine.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_id})
        now = float(connection.execute(text('SELECT EXTRACT(EPOCH FROM clock_timestamp())')).scalar_one())
        stored = connection.execute(text('SELECT events FROM security_buckets WHERE id=:id'), {'id': bucket}).scalar_one_or_none()
        if stored is None:
            # Serialize allocation only; existing visitors retain independent
            # locks. Fail closed rather than grow a free database without bound.
            connection.execute(text('SELECT pg_advisory_xact_lock(-714205886)'))
            count=connection.execute(text('SELECT COUNT(*) FROM security_buckets')).scalar_one()
            if count>=8192:
                return False
        events = [stamp for stamp in json.loads(stored or '[]') if now-stamp < seconds]
        accepted = len(events) < limit
        if accepted:
            events.append(now)
        connection.execute(text('INSERT INTO security_buckets (id,events,updated_at) VALUES (:id,:events,:now) '
                                'ON CONFLICT (id) DO UPDATE SET events=EXCLUDED.events,updated_at=EXCLUDED.updated_at'),
                           {'id': bucket, 'events': json.dumps(events), 'now': now_iso()})
        return accepted


async def run_exclusive(name, operation):
    owner = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        acquired = connection.execute(text(
            'INSERT INTO job_leases (id,owner,expires_at) VALUES (:id,:owner,:expires) '
            'ON CONFLICT (id) DO UPDATE SET owner=EXCLUDED.owner,expires_at=EXCLUDED.expires_at '
            'WHERE job_leases.expires_at<:now RETURNING id'),
            {'id': name, 'owner': owner, 'expires': (now+timedelta(minutes=10)).isoformat(), 'now': now.isoformat()}).scalar_one_or_none()
    if not acquired:
        return {'status': 'already running', 'added': 0}
    try:
        return await operation()
    finally:
        with engine.begin() as connection:
            connection.execute(text('DELETE FROM job_leases WHERE id=:id AND owner=:owner'), {'id': name, 'owner': owner})


async def cloud_audio(id, generate):
    with Session() as db:
        if db.get(AudioCache, id):
            return
    data = await generate()
    # Keep narration below both the function response limit and the free
    # database's intended small-object workload. The client already chunks text.
    if not data or len(data) > 3_500_000:
        raise HTTPException(413, 'Please select a shorter narration section.')
    with engine.begin() as connection:
        from sqlalchemy.dialects.postgresql import insert
        connection.execute(insert(AudioCache).values(id=id, data=data).on_conflict_do_nothing())


def check_cron(request, secret):
    import hmac
    expected = 'Bearer '+secret
    supplied = request.headers.get('authorization', '')
    if len(secret)<32 or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, 'Unauthorized scheduled request.')


def cleanup_limits():
    with engine.begin() as connection:
        connection.execute(text('DELETE FROM security_buckets WHERE updated_at<:cutoff'),
                           {'cutoff': (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()})
