import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env.local')
load_dotenv(ROOT / '.env')
# Reuse the user's existing workspace configuration without copying secrets.
load_dotenv(ROOT.parent / '.env.local')
SERVERLESS = os.getenv('VERCEL') == '1'
DATA = Path(os.getenv('NEWSROOM_DATA_DIR', '/tmp/newsroom' if SERVERLESS else str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
OPENAI_KEY = os.getenv('OPENAI_API_KEY', '')
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
TTS_MODEL = os.getenv('OPENAI_TTS_MODEL', 'gpt-4o-mini-tts')
YOUTUBE_KEY = os.getenv('YOUTUBE_API_KEY', '')
GEMINI_KEY = os.getenv('GEMINI_API_KEY', '')
VIDEO_MODEL = os.getenv('GEMINI_VIDEO_MODEL', 'gemini-3.5-flash-lite')
ADMIN_TOKEN = os.getenv('NEWSROOM_ADMIN_TOKEN', '')
TIMEZONE = os.getenv('NEWSROOM_TIMEZONE', 'Europe/London')
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA / "newsroom.db"}')
if DATABASE_URL.startswith(('postgres://', 'postgresql://')):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL.split('://', 1)[1]
if SERVERLESS and DATABASE_URL.startswith('sqlite'):
    raise RuntimeError('Vercel requires the connected durable database.')
STRIPE_KEY=os.getenv('STRIPE_SECRET_KEY','')
STRIPE_WEBHOOK_SECRET=os.getenv('STRIPE_WEBHOOK_SECRET','')
PUBLIC_APP_URL=os.getenv('PUBLIC_APP_URL','http://127.0.0.1:8788').rstrip('/')
ALLOW_REMOTE_REGISTRATION=os.getenv('NEWSROOM_ALLOW_REMOTE_REGISTRATION','false').lower()=='true'
PROXY_SECRET=os.getenv('NEWSROOM_PROXY_SECRET','')
CSRF_KEY=os.getenv('NEWSROOM_CSRF_SECRET','')
CRON_SECRET=os.getenv('CRON_SECRET','')
DEPLOYMENT_ORIGIN='https://'+os.environ['VERCEL_URL'] if SERVERLESS and os.getenv('VERCEL_URL') else ''
