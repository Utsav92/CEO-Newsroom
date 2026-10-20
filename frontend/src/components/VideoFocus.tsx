import {useEffect,useState} from 'react';
import {ArrowUpRight,Video as VideoIcon,X} from 'lucide-react';
import {request,type Video,type CEO} from '../api';
import {CEOAvatar} from './CEOAvatar';

export function VideoFocus({video,ceos,topic,onTopic,related,onRelated,onClear,onAsk,disabled}:{video:Video;ceos:CEO[];topic:string;onTopic:(value:string)=>void;related:boolean;onRelated:(value:boolean)=>void;onClear:()=>void;onAsk:(value:string)=>void;disabled:boolean}){
 const [connected,setConnected]=useState<boolean|null>(null);
 useEffect(()=>{let active=true;request<{configured:boolean}>('/video-understanding/status').then(s=>{if(active)setConnected(s.configured)}).catch(()=>{if(active)setConnected(null)});return()=>{active=false}},[]);
 return <section className="article-focus video-focus" aria-label="Selected video">
  <div className="focus-topline"><span><VideoIcon size={14}/> VIDEO CONVERSATION</span><button className="icon-button" aria-label="Clear selected video" onClick={onClear} disabled={disabled}><X size={16}/></button></div>
  <div className="video-focus-heading">{video.thumbnail&&<img src={video.thumbnail} alt="" referrerPolicy="no-referrer"/>}<div><h2><a href={video.url} target="_blank" rel="noopener noreferrer">{video.title}<ArrowUpRight size={16}/></a></h2><p className="focus-source">{video.company} · Official YouTube</p></div></div>
  <div className="focus-presenters"><CEOAvatar ceo={ceos.find(c=>c.id===video.presenter)} size={30}/><span>Chat with {ceos.find(c=>c.id===video.presenter)?.name||video.company+' CEO'}. Relevant companies can join with their own perspective.</span></div>
  <p className="video-understanding-note">Ask about the spoken explanation, a demonstration, a slide, or a specific moment such as 02:30. The app analyzes audio and visuals before preparing the answer.</p>
  {connected===false&&<p className="video-connection-needed" role="status">Video understanding needs to be connected in server settings. Your official video feed is connected.</p>}
  <label className="focus-topic">Topic to explore<input aria-label="Video topic" placeholder="e.g. the robot demonstration or the chart at 02:30" value={topic} maxLength={160} disabled={disabled} onChange={e=>onTopic(e.target.value)}/></label>
  <label className="focus-related"><input type="checkbox" checked={related} disabled={disabled} onChange={e=>onRelated(e.target.checked)}/>Include related reporting and live research</label>
  <div className="focus-prompts">{['Explain what is shown and said, and how it works.','How does this benefit each company involved?','What does the demonstration establish, and what are its limits?'].map(q=><button key={q} disabled={disabled} onClick={()=>onAsk(q)}>{q}<ArrowUpRight size={13}/></button>)}</div>
  <small>AI interpretations use approximate video timestamps. CEO avatars are simulations; company claims and possible impacts are qualified.</small>
 </section>
}
