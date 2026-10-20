"""Prepare or run Stripe's local test webhook relay without exposing API keys."""
import argparse,json,os,re,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from dotenv import dotenv_values,set_key

ROOT=Path(__file__).resolve().parents[1]
EVENTS='checkout.session.completed,checkout.session.async_payment_succeeded,invoice.paid,invoice.payment_failed,customer.subscription.updated,customer.subscription.deleted'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true',help='Save the local signing secret to ignored .env.local')
    parser.add_argument('--cli',help='Path to the official Stripe CLI executable')
    args=parser.parse_args()
    values={**dotenv_values(ROOT.parent/'.env.local'),**dotenv_values(ROOT/'.env.local')}
    key=os.environ.get('STRIPE_SECRET_KEY') or values.get('STRIPE_SECRET_KEY','')
    if not key.startswith(('sk_test_','rk_test_')):raise SystemExit('Configure a Stripe test secret or restricted key first.')
    executable=args.cli or shutil.which('stripe')
    if not executable:
        local=ROOT/'output'/'stripe-cli'/'stripe.exe'
        if local.exists():executable=str(local)
    if not executable:raise SystemExit('Install the official Stripe CLI, or pass its path with --cli. See docs/payments.md.')
    env={**os.environ,'STRIPE_API_KEY':key,'STRIPE_DEVICE_NAME':'CEO-Newsroom-local','STRIPE_NO_AUTO_UPDATE':'1'}
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    if args.prepare:
        result=subprocess.run([executable,'listen','--print-secret'],env=env,capture_output=True,text=True,timeout=50,**flags)
        found=re.search(r'whsec_[A-Za-z0-9]+',result.stdout)
        if result.returncode or not found:
            if 'stripecli_session_write' in result.stdout+result.stderr:
                raise SystemExit('Stripe requires Debugging Tools: Write (stripecli_session_write) on this restricted key. Enable it in Stripe, then retry.')
            raise SystemExit('Stripe CLI could not prepare the webhook relay. Check CLI access and restricted-key permissions.')
        set_key(str(ROOT/'.env.local'),'STRIPE_WEBHOOK_SECRET',found.group())
        print('Local test webhook signing secret saved. Keep the relay running while testing payments.')
        return
    expected=os.environ.get('STRIPE_WEBHOOK_SECRET') or values.get('STRIPE_WEBHOOK_SECRET','')
    if not expected:raise SystemExit('Run this helper with --prepare first.')
    folder=ROOT/'output';folder.mkdir(exist_ok=True)
    status=folder/'stripe-local-status.json'
    def state(ready,pid=None):status.write_text(json.dumps({'ready':ready,'pid':pid,'updated_at':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
    state(False)
    process=subprocess.Popen([executable,'listen','--forward-to','http://127.0.0.1:8788/api/billing/webhook','--events',EVENTS,'--events-from','@self'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',**flags)
    try:
        for line in process.stdout:
            found=re.search(r'whsec_[A-Za-z0-9]+',line)
            if found:
                if found.group()!=expected:raise RuntimeError('Webhook secret changed. Stop the app, rerun --prepare, and restart the app and relay.')
                state(True,process.pid)
            # CLI event IDs/status are useful; API and signing keys never reach logs.
            safe=line.replace(key,'[redacted]').replace(expected,'[redacted]')
            safe=re.sub(r'(?:whsec_|[srp]k_(?:test|live)_)[A-Za-z0-9]+','[redacted]',safe)
            print(safe.rstrip(),flush=True)
        raise SystemExit(process.wait())
    finally:
        state(False)
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()

if __name__=='__main__':main()
