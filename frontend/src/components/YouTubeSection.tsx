import {useEffect,useRef,useState,type FormEvent} from 'react';
import {ArrowUpRight,Check,Play,RefreshCw,Search,ShieldCheck,Video as VideoIcon} from 'lucide-react';
import {VideoChatButton} from './VideoChatButton';
import {request,type CEO,type Video,type YouTubeResult,type YouTubeStatus} from '../api';

export function YouTubeSection({ceos,company,onCompany,timezone,onPlay,onAsk,savedVideoIds=[]}:{savedVideoIds?:string[];ceos:CEO[];company:string;onCompany:(company:string)=>void;timezone:string;onPlay:(video:Video)=>void;onAsk:(video:Video)=>void}){
 const [query,setQuery]=useState('');const [result,setResult]=useState<YouTubeResult|null>(null);const [status,setStatus]=useState<YouTubeStatus|null>(null);const [loading,setLoading]=useState(true);const [error,setError]=useState('');const version=useRef(0);const searchRef=useRef('');
 const stamp=(value:string|null)=>value?new Date(value).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:timezone}):'Not checked yet';
 async function load(search='',refresh=false,background=false){
  const current=++version.current;if(!background)setLoading(true);setError('');searchRef.current=search;
  const responses=await Promise.allSettled([refresh?request<YouTubeResult>('/youtube/refresh',{company}):request<YouTubeResult>('/youtube/search?'+new URLSearchParams({company,q:search})),request<YouTubeStatus>('/youtube/status')]);
  if(current!==version.current)return;
  if(responses[1].status==='fulfilled')setStatus(responses[1].value);
  if(responses[0].status==='fulfilled'){
   const next=responses[0].value;
   const words=search.toLowerCase().split(/\s+/).filter(Boolean);
   if(refresh&&words.length)next.videos=next.videos.filter(v=>words.every(word=>(v.title+' '+(v.description||'')+' '+v.company).toLowerCase().includes(word)));
   setResult(next);
  }else{setError(responses[0].reason instanceof Error?responses[0].reason.message:'YouTube could not be loaded.');if(!background)setResult(null)}
  setLoading(false);
 }
 useEffect(()=>{setQuery('');setResult(null);void load();const timer=setInterval(()=>void load(searchRef.current,false,true),60000);return()=>{clearInterval(timer);++version.current}},[company]);
 function search(e:FormEvent){e.preventDefault();void load(query.trim())}
 const channels=result?.channels||status?.channels||[];
 return <section className="youtube-section" aria-label="Official company YouTube uploads">
  <div className="youtube-policy"><span><ShieldCheck size={15}/>Official company channels only</span><small>Updates daily</small></div>
  <p className="youtube-chat-intro">Chat with a CEO about the audio, visuals, or a specific moment in any video. Continue your conversation later in Chats.</p>
  <form className="filter-row video-filters" onSubmit={search}><select aria-label="Video company" value={company} onChange={e=>onCompany(e.target.value)}><option value="all">All companies</option>{ceos.map(c=><option key={c.id}>{c.company}</option>)}</select><label className="search-box"><Search size={15}/><input aria-label="Search official videos" placeholder="Search official uploads" value={query} maxLength={120} onChange={e=>setQuery(e.target.value)}/></label><button className="secondary-button" disabled={loading}>Search</button><button type="button" className="secondary-button" disabled={loading||!status?.configured} onClick={()=>void load(query.trim(),true)}><RefreshCw size={14} className={loading?'spinning':''}/>Refresh uploads</button></form>
  {result&&<div className="youtube-sync"><span>{result.videos.length} official uploads · Updated {stamp(result.updated_at)}</span>{status?.next_run&&<span>Next daily check {stamp(status.next_run)}</span>}</div>}
  {result?.warnings.length? <div className="youtube-warning" role="status"><strong>Some channels could not update.</strong><span>Showing previously verified uploads where available.</span><details><summary>See channel status</summary>{result.warnings.map(w=><p key={w}>{w}</p>)}</details></div>:null}
  {error&&<div className="empty-state" role="alert"><VideoIcon size={35}/><h3>{status?.configured?'YouTube is temporarily unavailable.':'Connect your official video feed.'}</h3><p>{error}</p>{!status?.configured&&<a className="secondary-button" href="https://developers.google.com/youtube/v3/getting-started" target="_blank" rel="noopener noreferrer">YouTube API setup<ArrowUpRight size={14}/></a>}<button className="secondary-button" disabled={loading} onClick={()=>void load(query.trim())}><RefreshCw size={14}/>Try again</button></div>}
  {loading&&!result?<div className="loading-state"><RefreshCw size={18} className="spinning"/>Checking official uploads…</div>:result?.videos.length?<div className="video-grid">{result.videos.map(v=><article className="video-card" key={v.id} data-company={v.company}><button className="video-open" aria-label={"Play "+v.title} onClick={()=>onPlay(v)}><div>{v.thumbnail&&<img src={v.thumbnail} alt="" loading="lazy" referrerPolicy="no-referrer"/>}<span className="video-play"><Play size={21}/></span></div><span className="video-official"><Check size={11}/>{v.company} · Official</span><h3>{v.title}</h3><p>{v.channel} · {new Date(v.published_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:timezone})}</p></button><VideoChatButton video={v} ceos={ceos} resume={savedVideoIds.includes(v.id)} onClick={()=>onAsk(v)}/></article>)}</div>:!error&&!loading?<div className="empty-state"><VideoIcon size={30}/><h3>{query?'No official uploads match this search.':'No public uploads available yet.'}</h3><p>{query?'Search titles and descriptions in the latest 50 uploads per company.':'Each channel is checked daily. No fan videos or example content are substituted.'}</p></div>:null}
  {channels.length>0&&<details className="youtube-channels"><summary>Official channels ({channels.length})</summary>{channels.map(c=><div key={c.company}><a href={c.channel_url} target="_blank" rel="noopener noreferrer">{c.company}<span>@{c.handle}</span><ArrowUpRight size={13}/></a><span>{c.status==='available'?'Checked':c.status==='unavailable'?'Update unavailable':'Not checked'}<small>{stamp(c.last_success_at)}</small></span></div>)}</details>}
  <p className="youtube-runtime-note">Daily checks run while your newsroom server is running. Reopening catches up on missed updates. Videos play on YouTube’s player; some uploads may require watching on YouTube.</p>
 </section>
}
