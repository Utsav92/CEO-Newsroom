import {useState,useEffect,useRef} from 'react';
import {MessageCircle,Search,RefreshCw} from 'lucide-react';
import type {ChatSummary,CEO} from '../api';

export function ChatHistory({sessions,current,loading,error,disabled,hasMore,ceos,onOpen,onRefresh,onMore}:{sessions:ChatSummary[];current:string;loading:boolean;error:string;disabled:boolean;hasMore:boolean;ceos:CEO[];onOpen:(id:string)=>void;onRefresh:()=>void;onMore:()=>void}){
 const [search,setSearch]=useState('');
 const panel=useRef<HTMLElement>(null);
 useEffect(()=>{const frame=requestAnimationFrame(()=>panel.current?.scrollIntoView({behavior:'smooth',block:'start'}));return ()=>cancelAnimationFrame(frame)},[]);
 const filtered=sessions.filter(s=>(s.title+' '+s.preview).toLowerCase().includes(search.toLowerCase().trim()));
 return <section ref={panel} className="chat-history-panel" aria-label="Saved chat history">
  <div className="chat-history-title"><div><h2>Chat history</h2><p>Your conversations are saved automatically.</p></div><button className="icon-button" aria-label="Refresh chat history" onClick={onRefresh} disabled={loading}><RefreshCw size={15} className={loading?'spinning':''}/></button></div>
  <label className="chat-history-search"><Search size={14}/><input aria-label="Search chat history" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Find an article or conversation"/></label>
  {error&&<p className="chat-history-error" role="alert">{error}</p>}
  {loading&&!sessions.length?<p className="chat-history-empty">Loading saved conversations…</p>:filtered.length?<div className="chat-history-list">{filtered.map(s=><button key={s.id} className={`chat-history-item ${current===s.id?'selected':''}`} aria-pressed={current===s.id} disabled={disabled} onClick={()=>onOpen(s.id)}><MessageCircle size={15}/><div><strong>{s.title}</strong><span>{s.preview}</span><small>{s.video_id?'Video · ':s.article_id?'Article · ':''}{ceos.find(c=>c.id===s.presenter)?.company||'Newsroom'} · {s.message_count} messages · {new Date(s.updated_at).toLocaleDateString('en-GB',{day:'numeric',month:'short'})}</small></div></button>)}</div>:<p className="chat-history-empty">{search?'No conversations match this search.':'Your conversations will appear here after the first answer.'}</p>}
  {hasMore&&<button className="secondary-button history-load-more" onClick={onMore} disabled={loading}>{loading?'Loading…':'Load older chats'}</button>}
 </section>
}
