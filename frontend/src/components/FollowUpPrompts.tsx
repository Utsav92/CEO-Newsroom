import {ArrowUpRight,MessageCircle} from 'lucide-react';
import type {CEO,Message} from '../api';

export function FollowUpPrompts({message,ceo,active,disabled,onAsk}:{message:Message;ceo?:CEO;active:boolean;disabled:boolean;onAsk:(question:string,message:Message)=>void}){
 if(!message.follow_up_question)return null;
 return <section className="answer-followup" aria-label={`${ceo?.name||'The Newsroom'} follow-up`}>
  <div className="followup-byline"><MessageCircle size={14}/>{ceo?`${ceo.name.split(' ')[0]} asks`:'A question for you'}</div>
  <p className="followup-question">{message.follow_up_question}</p>
  {active&&<>
   <div className="followup-replies" aria-label="Suggested replies">{message.reply_options?.map(reply=><button key={reply} disabled={disabled} onClick={()=>onAsk(reply,message)}>{reply}<ArrowUpRight size={12}/></button>)}</div>
   <small className="followup-hint">Choose a reply or type your own answer below.</small>
   {!!message.suggested_questions?.length&&<div className="followup-next"><span>Explore next</span>{message.suggested_questions.map(question=><button key={question} disabled={disabled} onClick={()=>onAsk(question,message)}>{question}<ArrowUpRight size={13}/></button>)}</div>}
  </>}
 </section>
}
