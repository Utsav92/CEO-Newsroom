import {useState,type FormEvent} from 'react';
import {Check,Eye,EyeOff,LogOut} from 'lucide-react';
import {request,resetAuthorization} from '../api';
import {useAccount,type AccountUser} from './AccountAccess';

export function ProfileSettings(){
 const {user,update,logout}=useAccount();
 const [name,setName]=useState(user.name);
 const [current,setCurrent]=useState('');const [next,setNext]=useState('');const [confirm,setConfirm]=useState('');
 const [show,setShow]=useState(false);const [busy,setBusy]=useState('');
 const [error,setError]=useState('');const [message,setMessage]=useState('');
 async function saveName(event:FormEvent){
  event.preventDefault();setBusy('profile');setError('');setMessage('');
  try{const data=await request<{user:AccountUser}>('/auth/profile',{name},'PUT');update(data.user);setName(data.user.name);setMessage('Your profile is saved.')}
  catch(e){setError((e as Error).message)}finally{setBusy('')}
 }
 async function password(event:FormEvent){
  event.preventDefault();setError('');setMessage('');
  if(next!==confirm){setError('The new passwords don’t match. Enter them again.');return}
  setBusy('password');
  try{const data=await request<{user:AccountUser}>('/auth/password',{current_password:current,new_password:next});resetAuthorization();update(data.user);setCurrent('');setNext('');setConfirm('');setShow(false);setMessage('Password updated. Your other sessions have been signed out.')}
  catch(e){setError((e as Error).message)}finally{setBusy('')}
 }
 return <section className="account-setting-content"><h3>Your account</h3>
  <form className="account-edit-form" onSubmit={e=>void saveName(e)}>
   <label>Your name<input value={name} onChange={e=>setName(e.target.value)} autoComplete="name" minLength={1} maxLength={80} required disabled={!!busy}/></label>
   <div className="account-email"><span>Email address</span><strong>{user.email}</strong></div>
   <button className="secondary-button" disabled={!!busy||name.trim()===user.name}>{busy==='profile'?'Saving…':'Save profile'}<Check size={15}/></button>
  </form>
  <details className="account-disclosure"><summary>Change password</summary>
   <form className="account-edit-form" onSubmit={e=>void password(e)}>
    <p>Use at least 12 characters. Changing your password signs out other sessions and keeps this one open.</p>
    <label>Current password<input type={show?'text':'password'} autoComplete="current-password" value={current} onChange={e=>setCurrent(e.target.value)} maxLength={128} required disabled={!!busy}/></label>
    <label>New password<input type={show?'text':'password'} autoComplete="new-password" value={next} onChange={e=>setNext(e.target.value)} minLength={12} maxLength={128} required disabled={!!busy}/></label>
    <label>Confirm new password<input type={show?'text':'password'} autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} minLength={12} maxLength={128} required disabled={!!busy}/></label>
    <button type="button" className="secondary-button" aria-pressed={show} onClick={()=>setShow(!show)}>{show?<EyeOff size={15}/>:<Eye size={15}/>} {show?'Hide passwords':'Show passwords'}</button>
    <button className="primary-button" disabled={!!busy}>{busy==='password'?'Updating password…':'Update password'}<Check size={16}/></button>
   </form>
  </details>
  {error&&<p role="alert" className="account-error">{error}</p>}
  {message&&<p role="status" className="account-success"><Check size={15}/>{message}</p>}
  <p>Chats, saved articles, and preferences belong to your account. Signing out keeps them saved here.</p>
  <button className="secondary-button account-logout" disabled={!!busy} onClick={async()=>{setBusy('logout');setError('');try{await logout()}catch(e){setError((e as Error).message);setBusy('')}}}><LogOut size={16}/>{busy==='logout'?'Signing out…':'Sign out'}</button>
 </section>;
}
