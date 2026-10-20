"""Send the app's authorized server settings through CLI stdin; never print secrets."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
TEAM='team_kQO2OCvxgbVUqnrjmbTWszTb'
PROJECT='prj_ZSrFthcMq9Dc1wZPC23IOWM4zOtz'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli',required=True,help='Installed Vercel CLI JavaScript entrypoint')
    args=parser.parse_args()
    cli=['node',args.cli]
    settings={**dotenv_values(ROOT.parent/'.env.local'),**dotenv_values(ROOT/'.env.local')}
    secret_file=ROOT/'output'/'vercel-app-secrets.env'
    generated=dotenv_values(secret_file) if secret_file.exists() else {}
    for name in ('NEWSROOM_CSRF_SECRET','CRON_SECRET'):
        generated.setdefault(name,secrets.token_hex(32))
    secret_file.write_text(''.join(k+'='+v+'\n' for k,v in generated.items()),encoding='utf-8')
    values={k:settings[k] for k in ('OPENAI_API_KEY','YOUTUBE_API_KEY','GEMINI_API_KEY') if settings.get(k)}
    values.update(generated)
    values.update({'PUBLIC_APP_URL':'https://ceo-newsroom.vercel.app','NEWSROOM_ALLOW_REMOTE_REGISTRATION':'false'})
    for name in ('OPENAI_MODEL','OPENAI_TTS_MODEL','GEMINI_VIDEO_MODEL','NEWSROOM_TIMEZONE'):
        if settings.get(name):values[name]=settings[name]
    for name,value in values.items():
        kind='secret' if name.endswith(('KEY','SECRET')) else 'config'
        result=subprocess.run(cli+['env','add',name,'--environment','production','--type',kind,'--force','--yes','--scope',TEAM],
                              input=value,text=True,capture_output=True,cwd=ROOT)
        if result.returncode:
            print('Configuration failed for '+name+'; provider output retained privately.',file=sys.stderr)
            (ROOT/'output'/'vercel-config-error.log').write_text(result.stderr,encoding='utf-8')
            raise SystemExit(1)
        print('Configured '+name,flush=True)
    path=ROOT/'output'/'vercel-project-settings.json'
    path.write_text(json.dumps({'framework':'fastapi','outputDirectory':None,'buildCommand':None,'installCommand':None,'resourceConfig':{'fluid':True}}),encoding='utf-8')
    result=subprocess.run(cli+['api','/v9/projects/'+PROJECT+'?teamId='+TEAM,'--method','PATCH','--input',str(path)],
                          text=True,capture_output=True,cwd=ROOT)
    if result.returncode:
        raise SystemExit('Project settings update failed; no deployment attempted.')
    data=json.loads(result.stdout)
    print(json.dumps({'project':data.get('name'),'framework':data.get('framework'),'outputDirectory':data.get('outputDirectory')}))


if __name__=='__main__':main()
