"""Shared interactive follow-ups for chat, article and video CEO answers."""
import re

FOLLOW_UP_SCHEMA={
    'follow_up_question':{'type':'string','minLength':1,'maxLength':240},
    'reply_options':{'type':'array','minItems':2,'maxItems':3,'items':{'type':'string','minLength':1,'maxLength':120}},
    'suggested_questions':{'type':'array','minItems':2,'maxItems':3,'items':{'type':'string','minLength':1,'maxLength':180}},
}

FOLLOW_UP_INSTRUCTIONS=(
    'Make the conversation useful and interactive after answering. In follow_up_question, ask ONE concise question directly to the user that clarifies their goal, role, constraint, tradeoff, or next decision so the next response can move toward a solution. '
    'Use the actual question, answer and conversation context; do not ask again for information the user already gave or use generic "want more?" questions. '
    'Provide 2-3 short reply_options written as possible USER answers to that question, plus 2-3 suggested_questions written as useful next questions the USER can ask the assistant. '
    'Suggested questions should explore concrete options, evidence, tradeoffs or a practical action plan for the assigned company and topic. '
    'Progress from understanding the problem to priorities, possible solutions, and next steps. Keep choices optional; the user can type their own answer. '
    'Do not assume an uncertain event or partnership is established, introduce new unsupported claims, or ask for unnecessary personal information. '
)

def follow_up_fields(value,company='this topic'):
    """Malformed suggestions must not discard an otherwise useful answer."""
    def clean(item,limit):
        return re.sub(r'\s+',' ',item).strip()[:limit] if isinstance(item,str) else ''
    def choices(key,limit,defaults):
        result=[]
        for item in value.get(key,[]) if isinstance(value.get(key),list) else []:
            text=clean(item,limit)
            if text and text.casefold() not in {v.casefold() for v in result}:result.append(text)
            if len(result)==3:break
        return result if len(result)>=2 else defaults
    return {
        'follow_up_question':clean(value.get('follow_up_question'),240) or f'What are you trying to decide or improve about {company}?',
        'reply_options':choices('reply_options',120,['Understand the risks','Compare possible solutions','Build a practical action plan']),
        'suggested_questions':choices('suggested_questions',180,['What practical steps would help address this?','What evidence would change this assessment?','Which tradeoffs should be prioritized?']),
    }
