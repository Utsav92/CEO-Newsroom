import {ArrowUpRight,MessageCircle} from 'lucide-react';
import type {CEO,Video} from '../api';
import {CEOAvatar} from './CEOAvatar';

export function VideoChatButton({video,ceos,resume=false,onClick,className=''}:{video:Video;ceos:CEO[];resume?:boolean;onClick:()=>void;className?:string}){
 const ceo=ceos.find(c=>c.id===video.presenter)||ceos.find(c=>c.company===video.company);
 const name=ceo?.name||`${video.company} CEO`;
 return <button className={`video-chat-button ${className}`} aria-label={`${resume?'Continue chat':'Chat'} with ${name} about ${video.title}`} onClick={onClick}>
  <CEOAvatar ceo={ceo} size={30}/><span><strong>{resume?'Continue with':'Chat with'} {name}</strong><small><MessageCircle size={11}/>{resume?'Saved video conversation':'About this video · Saves in Chats'}</small></span><ArrowUpRight size={16}/>
 </button>
}
