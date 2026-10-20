"""Password accounts and revocable, server-side login sessions."""
import hashlib,secrets,hmac,re,uuid,time,threading
from collections import OrderedDict,deque
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,delete,update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException,Request,Response
from .database import Session,Account,LoginSession,User,Membership
from .account_context import LANGUAGES
from .config import ALLOW_REMOTE_REGISTRATION,SERVERLESS
from .security import loopback

SCRYPT_N=2**17
_hash_slots=threading.BoundedSemaphore(2)
attempts=OrderedDict()
_attempt_lock=threading.Lock()

def password_hash(password,salt=None):
    salt=salt or secrets.token_bytes(16)
    with _hash_slots:value=hashlib.scrypt(password.encode(),salt=salt,n=SCRYPT_N,r=8,p=1,maxmem=256*1024*1024,dklen=32)
    return f'scrypt${SCRYPT_N}$'+salt.hex()+'$'+value.hex()

def verify_password(password,stored):
    try:
        _,n,salt,expected=stored.split('$')
        with _hash_slots:value=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=int(n),r=8,p=1,maxmem=256*1024*1024,dklen=32)
        return hmac.compare_digest(value.hex(),expected)
    except (ValueError,TypeError):return False

def normalize_email(value):
    value=value.strip().casefold()
    if len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise HTTPException(422,'Enter a valid email address.')
    return value

def throttle(request,email):
    now=time.monotonic();ip=request.client.host if request.client else 'local'
    groups=[('ip:'+ip,20),('account:'+hashlib.sha256((ip+email).encode()).hexdigest(),6),('identity:'+hashlib.sha256(email.encode()).hexdigest(),30)]
    if SERVERLESS:
        from .security import request_limits
        for key,limit in groups:
            if not request_limits.allow(('auth',key),limit,900):
                raise HTTPException(429,'Too many account attempts. Try again in 15 minutes.',headers={'Retry-After':'900'})
        return
    with _attempt_lock:
        for key,limit in groups:
            queue=attempts.pop(key,deque())
            while queue and now-queue[0]>900:queue.popleft()
            attempts[key]=queue
            if len(queue)>=limit:raise HTTPException(429,'Too many account attempts. Try again in 15 minutes.',headers={'Retry-After':'900'})
            queue.append(now)
        while len(attempts)>8192:attempts.popitem(last=False)


def profile(db,account):
    user=db.get(User,account.user_id)
    return {'id':account.user_id,'name':user.name,'email':account.email,'language':account.language}

def session_user(request):
    token=request.cookies.get('newsroom_auth','')
    if not token or len(token)>150:return None
    with Session.begin() as db:
        row=db.get(LoginSession,hashlib.sha256(token.encode()).hexdigest())
        if not row:return None
        now=datetime.now(timezone.utc)
        if row.expires_at<=now.isoformat() or not row.last_seen_at or row.last_seen_at<=(now-timedelta(minutes=30)).isoformat():return None
        if row.last_seen_at<(now-timedelta(minutes=1)).isoformat():row.last_seen_at=now.isoformat()
        account=db.get(Account,row.user_id)
        return profile(db,account) if account else None

def login_cookie(db,request,response,user_id):
    token=secrets.token_urlsafe(40)
    db.execute(delete(LoginSession).where(LoginSession.expires_at<datetime.now(timezone.utc).isoformat()))
    old=request.cookies.get('newsroom_auth','')
    if old:db.execute(delete(LoginSession).where(LoginSession.token_hash==hashlib.sha256(old.encode()).hexdigest()))
    older=db.scalars(select(LoginSession).where(LoginSession.user_id==user_id).order_by(LoginSession.expires_at.desc()).offset(4)).all()
    for row in older:db.delete(row)
    db.add(LoginSession(last_seen_at=datetime.now(timezone.utc).isoformat(),token_hash=hashlib.sha256(token.encode()).hexdigest(),user_id=user_id,expires_at=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()))
    response.set_cookie('newsroom_auth',token,httponly=True,samesite='lax',secure=request.url.scheme=='https',max_age=604800,path='/')

def register(request,response,name,email,password,language='en'):
    local=loopback(request.client.host if request.client else '')
    if not local and not ALLOW_REMOTE_REGISTRATION:raise HTTPException(403,'Account creation is currently limited to this server.')
    email=normalize_email(email);throttle(request,email)
    if not 12<=len(password)<=128:raise HTTPException(422,'Use a password with 12–128 characters.')
    if language not in LANGUAGES:raise HTTPException(422,'Choose a supported language.')
    hashed=password_hash(password)
    try:
        with Session.begin() as db:
            if db.scalars(select(Account).where(Account.email==email)).first():raise HTTPException(409,'This email is already registered. Sign in instead.')
            first=db.query(Account).count()==0
            if first and (request.url.hostname not in ('localhost','127.0.0.1','::1','testserver') or not local):
                raise HTTPException(403,'Create the first account on this server before opening remote registration.')
            id='local' if first else str(uuid.uuid4())
            user=db.get(User,id)
            if user:user.name=name.strip()
            else:db.add(User(id=id,name=name.strip()));db.flush()
            account=Account(user_id=id,email=email,password_hash=hashed,language=language);db.add(account)
            db.add(Membership(user_id=id));db.flush();login_cookie(db,request,response,id)
            return {'user':profile(db,account)}
    except IntegrityError:raise HTTPException(409,'Account setup changed. Please try signing in or creating your account again.') from None

def login(request,response,email,password):
    email=normalize_email(email);throttle(request,email)
    with Session.begin() as db:
        account=db.scalars(select(Account).where(Account.email==email)).first()
        previous=account.password_hash if account else None
        valid=verify_password(password,account.password_hash) if account else verify_password(password,f'scrypt${SCRYPT_N}$'+('00'*16)+'$'+('00'*32))
        if not account or not valid:raise HTTPException(401,'Email or password is incorrect.')
        # Serialize session creation with password replacement, including a concurrent change.
        matched=db.execute(update(Account).where(Account.user_id==account.user_id,Account.password_hash==previous).values(password_hash=previous)).rowcount
        if matched!=1:raise HTTPException(409,'Your password changed during sign-in. Try again with your current password.')
        login_cookie(db,request,response,account.user_id)
        return {'user':profile(db,account)}

def logout(request,response):
    token=request.cookies.get('newsroom_auth','')
    with Session.begin() as db:db.execute(delete(LoginSession).where(LoginSession.token_hash==hashlib.sha256(token.encode()).hexdigest()))
    response.delete_cookie('newsroom_auth',path='/');return {'signed_out':True}


def update_profile(user_id,name):
    with Session.begin() as db:
        account=db.get(Account,user_id)
        if not account:raise HTTPException(401,'Sign in to update your profile.')
        db.get(User,user_id).name=name.strip()
        return {'user':profile(db,account)}


def change_password(user_id,request,response,current_password,new_password):
    with Session() as db:
        account=db.get(Account,user_id)
        if not account:raise HTTPException(401,'Sign in to change your password.')
        email=account.email;previous=account.password_hash
    throttle(request,email)
    if not verify_password(current_password,previous):raise HTTPException(400,'Your current password is incorrect.')
    if not 12<=len(new_password)<=128:raise HTTPException(422,'Use a new password with 12–128 characters.')
    if current_password==new_password:raise HTTPException(422,'Choose a password different from your current one.')
    hashed=password_hash(new_password)
    with Session.begin() as db:
        account=db.get(Account,user_id)
        matched=db.execute(update(Account).where(Account.user_id==user_id,Account.password_hash==previous).values(password_hash=hashed)).rowcount
        if matched!=1:raise HTTPException(409,'Your password changed in another session. Sign in again.')
        db.execute(delete(LoginSession).where(LoginSession.user_id==user_id))
        login_cookie(db,request,response,user_id)
        return {'user':profile(db,account),'other_sessions_revoked':True}
