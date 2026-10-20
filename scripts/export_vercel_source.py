"""Export only this app for Vercel, without Git metadata, secrets or local data."""
import json,os,shutil,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    target=Path(tempfile.mkdtemp(prefix='ceo-newsroom-deploy-'))
    exclude={'node_modules','dist','tests','__pycache__','.git','.venv','data','output','.agents'}
    count=0
    for folder in ('backend','frontend'):
        for directory,dirs,files in os.walk(ROOT/folder):
            dirs[:]=[d for d in dirs if d not in exclude]
            for name in files:
                if name.startswith('.env') or name.endswith(('.pyc','.db','.sqlite')):continue
                source=Path(directory)/name;destination=target/source.relative_to(ROOT)
                destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination);count+=1
    for name in ('app.py','pyproject.toml','requirements.txt','vercel.json','.python-version','.vercelignore'):
        shutil.copy2(ROOT/name,target/name);count+=1
    (target/'.vercel').mkdir()
    shutil.copy2(ROOT/'.vercel'/'project.json',target/'.vercel'/'project.json')
    report={'path':str(target),'files':count,'project_id':'prj_ZSrFthcMq9Dc1wZPC23IOWM4zOtz','git_metadata':False}
    (ROOT/'output'/'vercel-source-export.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
