export type CEO={id:string;name:string;company:string;color:string;voice:string;initials:string;avatar:string;simulation:boolean;aliases?:string[]};
export type Article={id:string;url:string;title:string;source:string;published_at:string|null;ingested_at:string;summary:string;excerpt:string;why_it_matters:string;companies:string[];topics:string[];presenters:string[];image:string|null;classification:string;summary_kind:string;source_kind?:string;video_id?:string};
export type EvidencePassage={id:string;article_id:string;kind:string;text:string;article_title:string;source:string;url:string;published_at:string|null;selected_article:boolean;source_kind?:string;timestamp_seconds?:number;modality?:string};
export type ExplanationSection={kind:string;title:string;text:string;basis:'reported'|'explanation'|'inference'|'not_supported';citations:Article[];evidence:EvidencePassage[]};
export type Message={language?:string;research?:{status:'web_and_sources'|'sources_only';checked_at:string;source_count:number;web_source_count:number;cached:boolean;note:string};follow_up_question?:string;reply_options?:string[];suggested_questions?:string[];answer_kind?:'source_based'|'analysis'|'prediction'|'general_explanation';assessment_note?:string;presenter:string;text:string;citations:Article[];article_id?:string;article_title?:string;topic?:string;company_perspective?:string;video_id?:string;video_title?:string;video_analysis?:{model:string;cached:boolean;limitations:string};explanation?:{sections:ExplanationSection[];evidence_note:string}};
export type Briefing={id:string;date:string;kind:string;timezone:string;articles:Article[];videos?:Video[];messages:Message[];empty:boolean;generated_at:string};
export type Source={id:string;name:string;url:string;kind:string;company?:string;status:string;detail:string;checked_at:string|null};
export type Preferences={companies:string[];topics:string[];saved:string[];personalization:boolean;timezone:string;briefing_time:string;evening_time:string;notifications:boolean;autoplay:boolean;voice:string;speed:number};
export type Health={openai_configured:boolean;youtube_configured:boolean;article_count:number;scheduler_running:boolean;timezone:string;last_ingestion:{added:number;sources_available:number;sources_total:number;ai_error:string|null}|null;model:string; jobs:{id:string;next_run:string}[]};
export type Video={id:string;title:string;channel:string;published_at:string;thumbnail:string;company:string;presenter:string;url:string;description?:string;channel_id?:string;channel_url?:string;official_handle?:string;official?:boolean;embeddable?:boolean};
export type YouTubeChannelState={company:string;handle:string;channel_url:string;channel_id:string|null;title:string;last_attempt_at:string|null;last_success_at:string|null;status:string;detail:string};
export type YouTubeStatus={configured:boolean;daily_refresh_time:string;timezone:string;next_run:string|null;channels:YouTubeChannelState[]};
export type YouTubeResult={videos:Video[];channels:YouTubeChannelState[];official:boolean;cached:boolean;updated_at:string|null;warnings:string[];daily_refresh_time:string;timezone:string};
export function resetAuthorization(){token='';tokenPromise=null}
let token='';
let tokenPromise:Promise<void>|null=null;
async function authorize(){
  if(token)return;
  if(!tokenPromise)tokenPromise=fetch('/api/session').then(r=>r.json()).then(d=>{token=d.token}).finally(()=>{tokenPromise=null});
  await tokenPromise;
}
export async function request<T>(url:string,body?:unknown,method='POST'):Promise<T>{
  if(body!==undefined)await authorize();
  const send=()=>fetch('/api'+url,body===undefined?{}:{method,headers:{'Content-Type':'application/json','X-Newsroom-Token':token},body:JSON.stringify(body)});
  let response=await send();
  if(response.status===403&&body!==undefined){token='';await authorize();response=await send()}
  if(response.status===401&&!url.startsWith('/auth/'))window.dispatchEvent(new Event('newsroom-auth-required'));
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(typeof data.detail==='string'?data.detail:`Request failed (${response.status})`)}
  return response.json();
}

export type ChatSummary={id:string;title:string;preview:string;created_at:string;updated_at:string;message_count:number;presenter:string;article_id:string|null;video_id:string|null};
export type SavedChat={id:string;messages:(Message&{role:string})[];article_context:Article|null;video_context:Video|null;topic:string;include_related:boolean;missing_article:boolean};
