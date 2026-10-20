import {useState} from 'react';
import {ArrowUpRight,Check,Download,RefreshCw} from 'lucide-react';
import {request} from '../api';

type Subscription={status:string;cancel_at_period_end:boolean;period_end:number|null;cancel_at:number|null};
type Invoice={id:string;number:string|null;status:string;created:number;due_date:number|null;amount_cents:number;amount_paid:number;currency:string;url:string|null;pdf_url:string|null};
type Order={id:string;plan:string;method:string;status:string;created_at:string;amount_cents:number|null;currency:string;url:string|null};
type History={orders:Order[];invoices:Invoice[];subscription:Subscription|null;next_cursor:string|null;warning:string;connected:boolean;note:string};
const methodNames:Record<string,string>={google_pay:'Google Pay',apple_pay:'Apple Pay',credit_card:'Credit card',debit_card:'Debit card',mastercard:'Mastercard',bank_transfer:'Bank transfer',qr_code:'QR code'};
function date(value:number|string|null){if(!value)return 'Date unavailable';return new Date(typeof value==='number'?value*1000:value).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'Europe/London'})}
function money(cents:number|null,currency:string){return cents===null?'Amount unavailable':new Intl.NumberFormat('en-US',{style:'currency',currency}).format(cents/100)}

export function BillingHistory({onChange}:{onChange:()=>void}){
 const [data,setData]=useState<History|null>(null);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 const [confirm,setConfirm]=useState(false);const [message,setMessage]=useState('');
 async function load(more=false){
  setBusy(true);setError('');
  try{const response=await request<History>('/billing/history'+(more&&data?.next_cursor?'?after='+encodeURIComponent(data.next_cursor):''));setData(old=>more&&old?{...response,invoices:[...old.invoices,...response.invoices.filter(i=>!old.invoices.some(existing=>existing.id===i.id))]}:response)}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 async function renewal(renew:boolean){
  setBusy(true);setError('');setMessage('');
  try{const result=await request<{subscription:Subscription}>('/billing/renewal',{renew});setData(old=>old?{...old,subscription:result.subscription}:old);setConfirm(false);setMessage(renew?'Monthly renewal is on.':'Renewal is off. Your subscription ends at the close of the billing period.');onChange()}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 const sub=data?.subscription;const manageable=sub&&['active','trialing','past_due','unpaid'].includes(sub.status);
 return <details className="account-disclosure billing-history" onToggle={e=>{if(e.currentTarget.open&&!data&&!busy)void load()}}>
  <summary>Billing history &amp; renewal</summary>
  <div className="billing-history-body">
   {busy&&<p role="status"><RefreshCw size={14} className="spinning"/>Updating billing details…</p>}
   {error&&<p className="account-error" role="alert">{error}</p>}
   {data?.warning&&<p className="account-error" role="alert">{data.warning} Your saved payment attempts are still shown below.</p>}
   {message&&<p className="account-success" role="status"><Check size={15}/>{message}</p>}
   {sub&&<section className="subscription-details"><h4>Your subscription</h4><p>Status: {sub.status.replaceAll('_',' ')}.</p><p>{sub.cancel_at_period_end?'Ends':'Next billing date'}: {date(sub.cancel_at||sub.period_end)}.</p>
    {manageable&&(sub.cancel_at_period_end?<button className="secondary-button" disabled={busy} onClick={()=>void renewal(true)}>Resume monthly renewal</button>:!confirm?<button className="secondary-button" disabled={busy} onClick={()=>setConfirm(true)}>Stop monthly renewal</button>:<div className="renewal-confirmation"><p>Stop renewal after this billing period? Your current subscription stays in place until {date(sub.period_end)}. No refund is issued here.</p><div><button className="secondary-button" disabled={busy} onClick={()=>setConfirm(false)}>Keep renewal on</button><button className="secondary-button" disabled={busy} onClick={()=>void renewal(false)}>Confirm stop renewal</button></div></div>)}
   </section>}
   <section><h4>Invoices</h4>{data&&!data.invoices.length&&<p>{data.connected?'No invoices yet. Paid and unpaid subscription invoices will appear here.':'Connect Stripe to retrieve your invoices. Checkout is currently disabled.'}</p>}
    <ul className="billing-records">{data?.invoices.map(i=><li key={i.id}><div><strong>{i.number||'Subscription invoice'}</strong><span>{date(i.created)} · {money(i.amount_cents,i.currency)}</span></div><span className="billing-status">{i.status.replaceAll('_',' ')}</span>{i.status==='open'&&i.due_date&&<small>Due {date(i.due_date)}</small>}<div className="billing-record-links">{i.url&&<a href={i.url} target="_blank" rel="noopener noreferrer">{i.status==='open'?'Pay invoice':'View invoice'}<ArrowUpRight size={13}/></a>}{i.pdf_url&&<a href={i.pdf_url} target="_blank" rel="noopener noreferrer">Download PDF<Download size={13}/></a>}</div></li>)}</ul>
    {data?.next_cursor&&<button className="secondary-button" disabled={busy} onClick={()=>void load(true)}>Load older invoices</button>}
   </section>
   <section><h4>Payment attempts</h4><p>{data?.note}</p>{data&&!data.orders.length&&<p>No payment attempts yet.</p>}
    <ul className="billing-records">{data?.orders.map(o=><li key={o.id}><div><strong className="plan-name">{o.plan} · {money(o.amount_cents,o.currency)}/month</strong><span>{date(o.created_at)} · {methodNames[o.method]||o.method}</span></div><span className="billing-status">{o.status.replaceAll('_',' ')}</span>{o.url&&<a href={o.url} target="_blank" rel="noopener noreferrer">Continue payment<ArrowUpRight size={13}/></a>}</li>)}</ul>
   </section>
   <button className="secondary-button" disabled={busy} onClick={()=>void load()}><RefreshCw size={14}/>Refresh billing history</button>
  </div>
 </details>;
}
