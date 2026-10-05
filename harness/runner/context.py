"""Cached rules and bounded guide excerpts selected from authorized snapshots."""
from harness.modes import managed_cards
import re
from copy import deepcopy


def excerpts(text, terms, budget=5000):
    sections=re.split(r'(?=^#{1,4} )',text,flags=re.MULTILINE)
    ranked=sorted(enumerate(sections),key=lambda item:(sum(term in item[1].lower() for term in terms),-item[0]),reverse=True)
    selected=[];remaining=budget
    for index,section in ranked:
        if remaining<=0:break
        value=section[:remaining]
        selected.append((index,value));remaining-=len(value)
    return '\n'.join(value for _,value in sorted(selected))


def enrich(runner, context, player):
    rules=runner.assets.get('rules.md',{}).get('content','')
    context['rules']={'text':rules[:8000],'truncated':len(rules)>8000,
                      'format':runner.configuration.get('format'),
                      'banlist':runner.configuration.get('banlist'),
                      'rules_version':runner.configuration.get('rules_version'),
                      'settings':deepcopy(runner.configuration.get('settings'))}
    terms=[card.get('name','').lower() for card in context.get('cards',{}).values() if card.get('name')]
    terms.extend([runner.state['phase'],(runner.state.get('pending_decision') or {}).get('window','')])
    terms=[term for term in terms if term]
    owners=[player] if player!='moderator' else ['agent']+(['human'] if managed_cards(runner.state['mode']) else [])
    context['guides']={}
    if player=='moderator':
        context['deck_inventory']={}
        for owner,details in runner.state['players'].items():
            if details['deck'] is None:continue
            context['deck_inventory'][owner]=sorted(
                [{'instance_id':card['instance_id'],'card_id':card['card_id'],
                  'name':details['cards'].get(str(card['card_id']),{}).get('name')}
                 for card in details['deck']],key=lambda card:(card['card_id'],card['instance_id']))
    for name,asset in runner.assets.items():
        if name.endswith('/guide.md') and any(name.startswith(f'decks/{owner}/') for owner in owners):
            context['guides'][name]={'excerpt':excerpts(asset['content'],terms),'snapshot':name}
    return context
