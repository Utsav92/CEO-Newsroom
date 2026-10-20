import {test} from 'node:test';
import assert from 'node:assert/strict';
import {questionPresenters,articlePresenters,videoPresenters} from '../src/presenterRouting.ts';

const ceos=[
 ['sam_altman','Sam Altman','OpenAI',['ChatGPT','Codex','GPT','Sora']],
 ['mark_zuckerberg','Mark Zuckerberg','Meta',['Facebook','Instagram','WhatsApp','Llama']],
 ['tim_cook','Tim Cook','Apple',['iPhone','iPad','Siri']],
 ['sundar_pichai','Sundar Pichai','Google',['Gemini','DeepMind','Android']],
 ['dario_amodei','Dario Amodei','Anthropic',['Claude','Claude Code']],
 ['aravind_srinivas','Aravind Srinivas','Perplexity',['Comet browser']],
 ['ted_sarandos','Ted Sarandos','Netflix',['Netflix Games']],
 ['jensen_huang','Jensen Huang','NVIDIA',['CUDA','GeForce','Blackwell']],
].map(([id,name,company,aliases])=>({id,name,company,aliases}));
const ids=(...args)=>questionPresenters(...args).map(c=>c.id);

test('video owner and title partners join explicit question companies, without description footer mentions',()=>{
 const video={presenter:'dario_amodei',title:'Anthropic partners with Google',description:'Follow us on Meta'};
 assert.deepEqual(videoPresenters('How would NVIDIA benefit?',ceos,video).map(c=>c.id),['sundar_pichai','dario_amodei','jensen_huang']);
 assert.deepEqual(videoPresenters('Why does that matter?',ceos,{presenter:'sam_altman',title:'Demo'},'', ['sam_altman','jensen_huang']).map(c=>c.id),['sam_altman','jensen_huang']);
});

test('each company question shows its own CEO',()=>{
 for(const ceo of ceos)assert.deepEqual(ids(`What is new at ${ceo.company}?`,ceos),[ceo.id]);
});
test('a company named in the question overrides a different selected company',()=>{
 assert.deepEqual(ids('What happened at NVIDIA today?',ceos,'Apple'),['jensen_huang']);
});
test('questions about company products identify the right CEO',()=>{
 assert.deepEqual(ids('What changed in ChatGPT?',ceos),['sam_altman']);
 assert.deepEqual(ids('What is new in Claude Code?',ceos),['dario_amodei']);
 assert.deepEqual(ids('Explain Gemini and CUDA news.',ceos),['sundar_pichai','jensen_huang']);
});
test('a comparison shows both responding CEOs',()=>{
 assert.deepEqual(ids('Compare OpenAI and Anthropic.',ceos,'Apple'),['sam_altman','dario_amodei']);
});
test('generic questions use the selected CEO',()=>{
 assert.deepEqual(ids('What is the latest?',ceos,'Netflix'),['ted_sarandos']);
});
test('a follow-up keeps the previous CEO',()=>{
 assert.deepEqual(ids('Why does that matter?',ceos,'',['jensen_huang']),['jensen_huang']);
});
test('a CEO can be addressed by name',()=>{
 assert.deepEqual(ids('Sam Altman, explain the latest research.',ceos),['sam_altman']);
});
test('unrelated words and general questions do not invent a CEO',()=>{
 assert.deepEqual(ids('Explain metadata in a pineapple database.',ceos),[]);
 assert.deepEqual(ids('What happened in tech?',ceos),[]);
 assert.deepEqual(ids('What happened in tech?',ceos,'',['jensen_huang']),[]);
});

test('shared article shows all its CEOs and any company explicitly asked about',()=>{
 const article={presenters:['sundar_pichai','dario_amodei']};
 assert.deepEqual(articlePresenters('Explain their partnership.',ceos,article).map(c=>c.id),['sundar_pichai','dario_amodei']);
 assert.deepEqual(articlePresenters('How would NVIDIA benefit?',ceos,article).map(c=>c.id),['sundar_pichai','dario_amodei','jensen_huang']);
});

test('article topic routes an additional company and followups keep both CEOs',()=>{
 assert.deepEqual(articlePresenters('Explain this topic.',ceos,{presenters:['jensen_huang']},'OpenAI training').map(c=>c.id),['sam_altman','jensen_huang']);
 assert.deepEqual(ids('What are their risks?',ceos,'',['sam_altman','jensen_huang']),['sam_altman','jensen_huang']);
});
