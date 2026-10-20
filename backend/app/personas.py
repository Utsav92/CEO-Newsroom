PERSONAS = [
    dict(id='sam_altman', name='Sam Altman', company='OpenAI', color='#64dba6', voice='alloy', handle='OpenAI', initials='O', terms=['openai','chatgpt','codex','sora','gpt']),
    dict(id='mark_zuckerberg', name='Mark Zuckerberg', company='Meta', color='#6a9eff', voice='ash', handle='Meta', initials='M', terms=['meta','facebook','instagram','whatsapp','llama','reality labs']),
    dict(id='tim_cook', name='Tim Cook', company='Apple', color='#c7cdd6', voice='ballad', handle='Apple', initials='A', terms=['apple','iphone','ipad','macbook','vision pro','siri','apple intelligence']),
    dict(id='sundar_pichai', name='Sundar Pichai', company='Google', color='#f4c967', voice='coral', handle='Google', initials='G', terms=['google','gemini','deepmind','android','waymo']),
    dict(id='dario_amodei', name='Dario Amodei', company='Anthropic', color='#dca780', voice='echo', handle='anthropic-ai', initials='A', terms=['anthropic','claude']),
    dict(id='aravind_srinivas', name='Aravind Srinivas', company='Perplexity', color='#67cbd4', voice='fable', handle='perplexity-ai', initials='P', terms=['perplexity','comet browser']),
    dict(id='ted_sarandos', name='Ted Sarandos', company='Netflix', color='#f2747c', voice='nova', handle='Netflix', initials='N', terms=['netflix','netflix games']),
    dict(id='jensen_huang', name='Jensen Huang', company='NVIDIA', color='#b8e36e', voice='onyx', handle='NVIDIA', initials='N', terms=['nvidia','jensen huang','cuda','geforce','blackwell','dgx','jetson','isaac sim','omniverse','nvidia drive','nvidia nim','nvidia gtc']),
]
BY_COMPANY = {p['company']: p for p in PERSONAS}
BY_ID = {p['id']: p for p in PERSONAS}
TOPICS = {
    'AI research': ['research','model','llm','benchmark','agent','artificial intelligence','embedding','claude','gemini','gpt'],
    'Product launches': ['launch','introducing','release','available','unveil','announce'],
    'Robotics': ['robot','robotics','autonomous','isaac','jetson'],
    'Business': ['business','partner','invest','acquisition','enterprise','billion'],
    'Earnings': ['earnings','revenue','quarter','financial results'],
    'Regulation': ['regulation','policy','safety','lawsuit','court','antitrust'],
}
PROTOTYPES = [
    'OpenAI ChatGPT Codex GPT Sora AI models research and developer APIs',
    'Meta Facebook Instagram WhatsApp Llama AI Reality Labs social networks',
    'Apple iPhone iPad Mac Vision Pro Siri Apple Intelligence devices',
    'Google Gemini DeepMind Android Google Cloud Waymo AI research',
    'Anthropic Claude Claude Code language models safety research',
    'Perplexity AI search Comet browser Computer answer engine',
    'Netflix streaming recommendations advertising games entertainment',
    'NVIDIA CUDA GeForce Blackwell Rubin GPUs DGX Isaac robotics Omniverse',
]
