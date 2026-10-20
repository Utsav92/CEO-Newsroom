import type {ReactNode} from 'react';
import type {Article,Message} from '../api';

const labels={reported:'Reported fact',explanation:'Explanation',inference:'Reasoned assessment',not_supported:'Detail unavailable'};
export function ExplanationAnswer({message,citation}:{message:Message;citation:(article:Article)=>ReactNode}){
 if(!message.explanation)return null;
 const words=[message.text,...message.explanation.sections.map(s=>s.text)].join(' ').trim().split(/\s+/).length;
 return <div className="article-explanation">
  {message.research&&<div className="research-coverage"><strong>{message.research.status==='web_and_sources'?'Live research + source analysis':'Source analysis'}</strong><span>{message.research.source_count} cited {message.research.source_count===1?'source':'sources'} · ~{Math.max(1,Math.ceil(words/200))} min read</span><small>{message.research.note}</small></div>}
  <div className="explanation-context">{message.company_perspective} perspective{(message.video_title||message.article_title)&&<span>From: {message.video_title||message.article_title}</span>}</div>
  {message.explanation.sections.map(section=><section className="explanation-section" key={section.kind}>
   <div><h3>{section.title}</h3><span className={`evidence-basis ${section.basis}`}>{section.basis==='reported'&&section.evidence.some(p=>p.source_kind==='video_analysis')?'Video observation':labels[section.basis]}</span></div>
   <p>{section.text}</p>
   <div className="answer-citations">{section.citations.map(a=>citation(a))}</div>
   {section.evidence.length>0&&<details className="retrieved-evidence"><summary>View source passages ({section.evidence.length})</summary>{section.evidence.map(p=><div key={p.id}><a href={p.url} target="_blank" rel="noopener noreferrer">{p.source} · {p.source_kind==='video_analysis'?`Video observation · ~${Math.floor((p.timestamp_seconds||0)/60)}:${String((p.timestamp_seconds||0)%60).padStart(2,'0')}`:p.source_kind==='web_research'?'AI synthesis of cited web source':p.source_kind==='web_document'?'Live source excerpt':p.source_kind==='video_metadata'?'Video metadata':p.selected_article?'Selected article':'Supporting report'}</a>{p.source_kind==='video_analysis'||p.source_kind==='web_research'?<p className="video-observation">{p.text}</p>:<blockquote>{p.text}</blockquote>}</div>)}</details>}
  </section>)}
  <p className="explanation-note">{message.explanation.evidence_note}</p>
 </div>
}

export function answerNarration(message:Message){return [message.text,...(message.explanation?.sections.map(s=>s.title+'. '+s.text)||[]),...(message.follow_up_question?[message.follow_up_question]:[])].join('\n\n')}
