import {createContext,useContext,useEffect,useState,type ReactNode,type FormEvent} from 'react';
import {ArrowRight,Eye,EyeOff,LockKeyhole,LogOut,MessageCircle,RefreshCw} from 'lucide-react';
import {request,resetAuthorization} from '../api';

export type AccountUser={id:string;name:string;email:string;language:string};
export const languages:Record<string,string>={en:'English',hi:'हिन्दी · Hindi',es:'Español · Spanish',fr:'Français · French',de:'Deutsch · German',ar:'العربية · Arabic',ja:'日本語 · Japanese',zh:'简体中文 · Chinese',pt:'Português · Portuguese',it:'Italiano · Italian',ko:'한국어 · Korean',bn:'বাংলা · Bengali'};
const AccountContext=createContext<{user:AccountUser;update:(u:AccountUser)=>void;logout:()=>Promise<void>}>({user:{id:'',name:'',email:'',language:'en'},update:()=>{},logout:async()=>{}});
export const useAccount=()=>useContext(AccountContext);

function clearPrivateState(){document.querySelectorAll('audio').forEach(a=>a.pause());for(const key of Object.keys(localStorage))if(key.startsWith('newsroom-'))localStorage.removeItem(key);resetAuthorization();const url=new URL(location.href);url.searchParams.delete('chat');url.searchParams.delete('view');url.searchParams.delete('settings');url.searchParams.delete('payment');history.replaceState(null,'',url)}

export function AccountAccess({children}:{children:ReactNode}){
 const [user,setUser]=useState<AccountUser|null>(null);const [loading,setLoading]=useState(true);const [first,setFirst]=useState(false);const [mode,setMode]=useState<'login'|'register'|'logout'>('login');const [error,setError]=useState('');
 useEffect(()=>{let live=true;request<{user:AccountUser|null;first_run:boolean}>('/auth/session').then(r=>{if(live){setUser(r.user);setFirst(r.first_run);if(r.first_run)setMode('register')}}).catch(e=>{if(live)setError(e.message)}).finally(()=>{if(live)setLoading(false)});return()=>{live=false}},[]);
 useEffect(()=>{const expired=()=>{clearPrivateState();setUser(null);setMode('login');setError('Your session has ended. Sign in to continue. Your saved conversations are still on the server.')};window.addEventListener('newsroom-auth-required',expired);return()=>window.removeEventListener('newsroom-auth-required',expired)},[]);
 async function logout(){await request('/auth/logout',{});clearPrivateState();setUser(null);setMode('logout');setError('')}
 if(loading)return <div className="account-loading" role="status"><RefreshCw size={22} className="spinning"/>Opening your newsroom…</div>;
 if(user)return <AccountContext.Provider value={{user,update:setUser,logout}}>{children}</AccountContext.Provider>;
 return <main className="account-access"><section className="account-story"><a className="account-brand" href="/"><MessageCircle size={29}/><span>CEO<br/><small>NEWSROOM</small></span></a><div><h1>In good <br/>company.</h1><p>The stories shaping technology.<br/>The conversations that help you understand them.</p><div className="account-faces" aria-label="AI CEO presenters">{['sam_altman','mark_zuckerberg','tim_cook','sundar_pichai','dario_amodei','aravind_srinivas','ted_sarandos','jensen_huang'].map(id=><img key={id} src={`/avatars/${id}_profile.png?v=3.0.3`} alt=""/>)}</div><p className="account-story-note">Read the reporting. Ask better questions.<br/>Pick up every conversation where you left it.</p></div><small>Independent reporting · AI-simulated presenters</small></section><section className="account-form-side">
  {mode==='logout'?<div className="account-form"><LogOut size={32}/><h2>You’re signed out.</h2><p>Your conversations and saved articles are waiting for you. Sign in whenever you’re ready to return.</p><button className="primary-button" onClick={()=>setMode('login')}>Back to sign in<ArrowRight size={17}/></button></div>:<LoginForm mode={mode} first={first} error={error} onMode={m=>{setMode(m);setError('')}} onSuccess={u=>{setUser(u);setError('');setFirst(false)}}/>}
 </section></main>;
}

function LoginForm({mode,first,error,onMode,onSuccess}:{mode:'login'|'register';first:boolean;error:string;onMode:(m:'login'|'register')=>void;onSuccess:(u:AccountUser)=>void}){
 const [name,setName]=useState('');const [email,setEmail]=useState('');const [password,setPassword]=useState('');const [language,setLanguage]=useState('en');const [show,setShow]=useState(false);const [busy,setBusy]=useState(false);const [localError,setError]=useState('');
 useEffect(()=>{setPassword('');setError('');setShow(false)},[mode]);
 async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError('');try{const r=await request<{user:AccountUser}>('/auth/'+(mode==='register'?'register':'login'),{email,password,...(mode==='register'?{name,language}:{})});resetAuthorization();onSuccess(r.user)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <form className="account-form" onSubmit={e=>void submit(e)}><div className="account-form-heading"><LockKeyhole size={24}/><h2>{mode==='register'?'Create your account.':'Welcome back.'}</h2><p>{mode==='register'?'Make room for your next good question.':'Sign in to your own saved conversations and articles.'}</p></div>
  {first&&mode==='register'&&<p className="account-first-note">Your first account keeps the articles and conversations already saved on this server.</p>}
  {mode==='register'&&<label>Your name<input autoComplete="name" value={name} onChange={e=>setName(e.target.value)} maxLength={80} required disabled={busy}/></label>}
  <label>Email address<input type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} maxLength={254} required disabled={busy}/></label>
  <label>Password<div className="password-field"><input type={show?'text':'password'} autoComplete={mode==='register'?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)} minLength={mode==='register'?12:1} maxLength={128} required disabled={busy}/><button type="button" className="icon-button" aria-label={show?'Hide password':'Show password'} onClick={()=>setShow(!show)}>{show?<EyeOff size={18}/>:<Eye size={18}/>}</button></div>{mode==='register'&&<small>Use at least 12 characters.</small>}</label>
  {mode==='register'&&<label>CEO answer language<select value={language} onChange={e=>setLanguage(e.target.value)}>{Object.entries(languages).map(([code,name])=><option key={code} value={code}>{name}</option>)}</select></label>}
  {(localError||error)&&<p className="account-error" role="alert">{localError||error}</p>}
  <button className="primary-button" disabled={busy}>{busy?'Please wait…':mode==='register'?'Create account':'Sign in'}{busy?<RefreshCw size={16} className="spinning"/>:<ArrowRight size={17}/>}</button>
  <p className="account-switch">{mode==='register'?'Already have an account?':'New to the newsroom?'} <button type="button" disabled={busy} onClick={()=>onMode(mode==='register'?'login':'register')}>{mode==='register'?'Sign in':'Create an account'}</button></p>
  <p className="account-storage-note">Your account and saved history stay on this newsroom server.</p>
 </form>;
}
