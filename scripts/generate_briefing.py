import sys, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.database import migrate
from app.services import generate_briefing
if __name__=='__main__':
    migrate(); print(json.dumps(generate_briefing(sys.argv[1] if len(sys.argv)>1 else 'morning'),indent=2))
