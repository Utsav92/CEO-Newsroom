import type {CEO,Article,Video} from './api';

export function videoPresenters(question:string,ceos:CEO[],video:Video,topic='',previousPresenters:string[]=[]):CEO[]{
  const named=questionPresenters(question+' '+topic,ceos,'',previousPresenters);
  const fromTitle=questionPresenters(video.title,ceos);
  const ids=new Set([video.presenter,...fromTitle.map(c=>c.id),...named.map(c=>c.id)]);
  return ceos.filter(c=>ids.has(c.id));
}

function mentions(text:string,alias:string){
  const escaped=alias.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  return new RegExp(`(^|[^\\p{L}\\p{N}_])${escaped}(?=$|[^\\p{L}\\p{N}_])`,'iu').test(text);
}

export function articlePresenters(question:string,ceos:CEO[],article:Article,topic='',previousPresenters:string[]=[]):CEO[]{
  const named=questionPresenters(question+' '+topic,ceos,'',previousPresenters);
  const ids=new Set([...article.presenters,...named.map(c=>c.id)]);
  return ceos.filter(c=>ids.has(c.id));
}

export function questionPresenters(question:string,ceos:CEO[],selectedCompany='',previousPresenters:string[]=[]):CEO[]{
  const named=ceos.filter(ceo=>[ceo.company,ceo.name,...(ceo.aliases||[])].some(alias=>mentions(question,alias)));
  if(named.length)return named;
  const followUp=/\b(that|this|it|those|these|they|their|more|why)\b|\bwhat about\b/i.test(question);
  if(followUp&&previousPresenters.length>1)return ceos.filter(ceo=>previousPresenters.includes(ceo.id));
  const selected=ceos.find(ceo=>ceo.company===selectedCompany);
  if(selected)return [selected];
  return followUp?ceos.filter(ceo=>previousPresenters.includes(ceo.id)):[];
}
