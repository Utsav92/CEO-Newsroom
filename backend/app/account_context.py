from contextvars import ContextVar

current_user=ContextVar('newsroom_current_user',default='local')
current_language=ContextVar('newsroom_current_language',default='en')
LANGUAGES={'en':'English','hi':'Hindi','es':'Spanish','fr':'French','de':'German','ar':'Arabic','ja':'Japanese','zh':'Simplified Chinese','pt':'Portuguese','it':'Italian','ko':'Korean','bn':'Bengali'}
