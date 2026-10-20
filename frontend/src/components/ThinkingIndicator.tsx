import type {CSSProperties} from 'react';
import {motion} from 'motion/react';
import type {CEO} from '../api';
import {CEOAvatar} from './CEOAvatar';

export function ThinkingIndicator({presenters,video=false}:{presenters:CEO[];video?:boolean}){
  const rows: (CEO|undefined)[]=presenters.length?presenters:[undefined];
  return <div className="thinking-presenters" role="status" aria-live="polite" aria-label={presenters.length?`${presenters.map(ceo=>ceo.name).join(' and ')} thinking and checking sources`:'The Newsroom is thinking and checking sources'}>
    {rows.map(ceo=><motion.div key={ceo?.id||'newsroom'} className="thinking-message" data-presenter={ceo?.id||'newsroom'} style={{'--company':ceo?.color||'#c6e9a8'} as CSSProperties} initial={{opacity:0,y:6}} animate={{opacity:1,y:0}}>
      <div className="thinking-avatar">
        <CEOAvatar ceo={ceo} size={44}/>
        <span className="thought-bubble" aria-hidden="true"><i/><i/><i/></span>
      </div>
      <div className="thinking-copy">
        <div className="message-byline"><strong>{ceo?.name||'The Newsroom'}</strong>{ceo&&<span className="presenter-company">{ceo.company}</span>}<span className="ai-label">AI presenter</span></div>
        <div className="thinking-caption"><span>{video?'Understanding and researching video…':'Researching your question…'}</span><span className="thinking-dots" aria-hidden="true"><i/><i/><i/></span></div>
        <small>{video?'Analyzing speech and visuals, checking context, and preparing a detailed explanation.':ceo?`Gathering evidence and examining mechanisms, trade-offs, and impact for ${ceo.company}.`:'Gathering sources and preparing a detailed explanation with evidence and limitations.'}</small>
      </div>
    </motion.div>)}
  </div>;
}
