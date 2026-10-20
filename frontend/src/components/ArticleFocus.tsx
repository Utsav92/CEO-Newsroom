import {ArrowUpRight,BookOpen,X} from 'lucide-react';
import type {Article,CEO} from '../api';
import {CEOAvatar} from './CEOAvatar';

export function ArticleFocus({article,ceos,timezone,topic,onTopic,related,onRelated,onClear,onAsk,disabled}:{article:Article;ceos:CEO[];timezone:string;topic:string;onTopic:(value:string)=>void;related:boolean;onRelated:(value:boolean)=>void;onClear:()=>void;onAsk:(value:string)=>void;disabled:boolean}){
 return <section className="article-focus" aria-label="Selected article">
  <div className="focus-topline"><span><BookOpen size={14}/> ASK THIS ARTICLE</span><button className="icon-button" aria-label="Clear selected article" onClick={onClear} disabled={disabled}><X size={16}/></button></div>
  <h2><a href={article.url} target="_blank" rel="noopener noreferrer">{article.title}<ArrowUpRight size={16}/></a></h2>
  <p className="focus-source">{article.source} · {article.published_at?new Date(article.published_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:article.published_at.length===10?'UTC':timezone}):'Publication date unavailable'}</p>
  <div className="focus-presenters">{article.presenters.map(id=><CEOAvatar key={id} ceo={ceos.find(c=>c.id===id)} size={30}/>)}<span>Each relevant company gets its own perspective.</span></div>
  <label className="focus-topic">Topic to explore<input aria-label="Article topic" placeholder="e.g. GPU supply, training costs, partnership benefits" value={topic} maxLength={160} disabled={disabled} onChange={e=>onTopic(e.target.value)}/></label>
  <div className="focus-tags">{article.topics.map(t=><button key={t} disabled={disabled} aria-pressed={topic===t} onClick={()=>onTopic(topic===t?'':t)}>{t}</button>)}</div>
  <label className="focus-related"><input type="checkbox" checked={related} disabled={disabled} onChange={e=>onRelated(e.target.checked)}/>Include related reporting and live research</label>
  <div className="focus-prompts">{['Explain this topic and how it works.','How does this benefit each company involved?','What could the impact and risks be?'].map(q=><button key={q} disabled={disabled} onClick={()=>onAsk(q)}>{q}<ArrowUpRight size={13}/></button>)}</div>
  <small>Answers retrieve publisher titles and available excerpts. Open the original for the full article.</small>
 </section>
}
