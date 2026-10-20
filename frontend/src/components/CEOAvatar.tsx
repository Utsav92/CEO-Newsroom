import type {CSSProperties} from 'react';
import {Radio} from 'lucide-react';
import type {CEO} from '../api';

export function CEOAvatar({ceo,size=42}:{ceo?:CEO;size?:number}){
  return ceo?
    <img className="avatar" src={`/avatars/${ceo.id}_profile.png?v=3.0.3`} alt={`${ceo.name}, AI simulation`} width={size} height={size} style={{'--company':ceo.color,'--avatar-size':size+'px'} as CSSProperties}/>:
    <div className="narrator-avatar" style={{width:size,height:size}}><Radio size={19}/></div>;
}
