"""Contract tests use queued structured outputs, NOT real LLM performance evidence."""
import pytest
from travel_agent.models import Plan, EvidenceBatch, Session, Preference, Query
from travel_agent.data import Database
from travel_agent.retrieval import HybridIndex
from travel_agent.agent import Agent
from travel_agent.grounding import Grounder
from travel_agent.llm import ModelUnavailable, JsonLLM

class QueuedProvider:
    def __init__(self,*responses): self.responses=list(responses); self.calls=[]
    def structured(self,system,payload,schema):
        self.calls.append((schema.__name__,payload))
        response=self.responses.pop(0)
        if isinstance(response,Exception): raise response
        return schema.model_validate(response)

@pytest.fixture(scope='module')
def resources():
    db=Database(); return db,HybridIndex(db)

def agent(resources,provider): return Agent(*resources,provider)

def test_progressive_clarification_and_memory(resources):
    provider=QueuedProvider(
        {'intent':'clarify','add_preferences':[{'concept':'experience','value':'relaxation'}],
         'question':'What kind of relaxing escape do you imagine, and do you have a destination in mind?'},
        {'intent':'clarify','add_preferences':[{'concept':'waterfront','value':'near the beach'}],
         'question':'Which destination would you like to explore?'})
    state=Session(); a=agent(resources,provider)
    a.respond('I want to relax and do nothing',state)
    out=a.respond('Near the beach',state)
    assert set(state.preferences)=={'experience','waterfront'}
    assert state.preferences['experience'].source_turn==1
    assert state.preferences['waterfront'].source_turn==2
    assert len(state.history)==4 and not state.last_ids
    assert out['trace']['clarification']
    assert 'relaxation' in str(provider.calls[1][1])

def test_updates_preserve_unrelated_state(resources):
    state=Session(preferences={'pool':Preference(concept='pool',value='pool'),
                              'family':Preference(concept='family',value='family')},
                  slots={'city':'Dubai','max_budget':300,'budget_hard':True})
    p=QueuedProvider({'intent':'clarify','remove_preferences':['pool'],
        'add_preferences':[{'concept':'access','value':'downtown','priority':5}],
        'slots':{'budget_hard':False},'question':'Any preferred downtown area?'})
    agent(resources,p).respond('Pool no longer matters; downtown is more important; budget can flex',state)
    assert set(state.preferences)=={'family','access'}
    assert state.slots['city']=='Dubai' and state.slots['max_budget']==300
    assert not state.slots['budget_hard'] and state.preferences['access'].priority==5

def test_reference_resolution_keeps_latest_recommendation_order(resources):
    rows=list(resources[0].records.values())[:3]; ids=[r['id'] for r in rows]
    state=Session(last_ids=ids)
    p=QueuedProvider({'intent':'query','references':[2],'query':{'operation':'detail'}})
    result=agent(resources,p).respond('Tell me about the second one',state)
    assert rows[1]['name'] in result['answer']
    assert state.focus_ids==[ids[1]] and state.last_ids==ids
    p.responses.append({'intent':'query','use_focus':True,'query':{'operation':'detail'},'requested_fields':['labels']})
    assert rows[1]['name'] in agent(resources,p).respond('Does it have a pool?',state)['answer']

def test_peak_comparison_uses_actual_values(resources):
    db=resources[0]; rows=list(db.records.values())[:3]
    state=Session(last_ids=[r['id'] for r in rows])
    p=QueuedProvider({'intent':'query','references':[1,2,3],
                     'query':{'operation':'list','price_field':'peak_price','limit':1}})
    result=agent(resources,p).respond('Which of those is cheapest in peak season?',state)
    assert result['trace']['retrieved_ids']==[min(rows,key=lambda r:(r['peak_price'],r['id']))['id']]

def test_no_match_budget_and_session_isolation(resources):
    p=QueuedProvider({'intent':'recommend','slots':{'city':'Dubai','max_budget':1,'budget_hard':True}})
    state=Session(); other=Session()
    result=agent(resources,p).respond('Dubai under $1',state)
    assert not result['cards'] and 'No records' in result['answer']
    assert not other.history and not other.slots

def test_invalid_reference_is_transactional(resources):
    state=Session(last_ids=[next(iter(resources[0].records))]); before=state.model_dump()
    p=QueuedProvider({'intent':'query','references':[8],'slots':{'city':'Dubai'}})
    with pytest.raises(ValueError): agent(resources,p).respond('eighth one',state)
    assert state.model_dump()==before

def test_provider_failure_preserves_state(resources):
    state=Session(); p=QueuedProvider(ModelUnavailable('offline'))
    with pytest.raises(ModelUnavailable): agent(resources,p).respond('hello',state)
    assert state.turn==0 and not state.history

def test_evidence_rejects_invented_quote_and_hotel(resources):
    db=resources[0]; row=next(iter(db.records.values()))
    p=QueuedProvider({'hotels':[
        {'id':row['id'],'evidence':[{'preference':'pool','field':'labels','relation':'hotel_property','quote':'unicorn moon spa'}]},
        {'id':'made_up','evidence':[{'preference':'pool','field':'labels','relation':'hotel_property','quote':row['labels']}]}]})
    evidence=Grounder(db,p).verify([row],[Preference(concept='pool',value='pool',hard=True)])
    assert evidence=={row['id']:[]}

def test_negated_requirement_needs_explicit_contradiction():
    from travel_agent.models import Evidence
    p=Preference(concept='pool',value='pool',negated=True,hard=True)
    assert not Grounder.satisfies(p,[])
    assert Grounder.satisfies(p,[Evidence(preference='pool',field='labels',relation='hotel_property',quote='No swimming pool',supports=False)])
    assert not Grounder.satisfies(p,[Evidence(preference='pool',field='labels',relation='hotel_property',quote='Swimming pool',supports=True)])

def test_real_grounded_recommendation_contract(resources):
    db=resources[0]
    row=next(r for r in db.records.values() if 'Swimming Pool' in r['labels'])
    p=QueuedProvider({'intent':'recommend','slots':{'city':row['city']},
                     'add_preferences':[{'concept':'pool','value':'a swimming pool','hard':True}],
                     'query':{'filters':[{'field':'id','op':'eq','value':row['id']}]}} ,
        {'hotels':[{'id':row['id'],'evidence':[{'preference':'pool','field':'labels','relation':'hotel_property','quote':'Swimming Pool'}]}]})
    state=Session(); result=agent(resources,p).respond('I need a pool',state)
    assert len(result['cards'])==1 and state.last_ids==[row['id']]
    assert 'Swimming Pool' in result['answer'] and 'not live' in result['answer']
    assert str(row['peak_price']).split('.')[0] in result['answer']

def test_unsupported_does_not_call_database(resources):
    p=QueuedProvider({'intent':'unsupported'})
    out=agent(resources,p).respond('Guarantee availability tomorrow',Session())
    assert 'does not establish live availability' in out['answer']
    assert len(p.calls)==1

def test_paid_api_guard(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','openai'); monkeypatch.delenv('ALLOW_PAID_API',raising=False)
    with pytest.raises(ModelUnavailable): JsonLLM()

def test_comparison_subset_and_order_memory(resources):
    rows=list(resources[0].records.values())[:3]; ids=[r['id'] for r in rows]
    state=Session(last_ids=ids)
    p=QueuedProvider({'intent':'query','references':[1,3],'query':{'operation':'compare'}},
                     {'intent':'query','use_focus':True,'query':{'operation':'list','price_field':'peak_price','limit':1}})
    a=agent(resources,p)
    a.respond('Compare the first and third',state)
    assert state.last_ids==ids and state.focus_ids==[ids[0],ids[2]]
    out=a.respond('Which is cheaper in peak season?',state)
    assert out['trace']['retrieved_ids']==[min([rows[0],rows[2]],key=lambda r:(r['peak_price'],r['id']))['id']]
    assert state.last_ids==ids

def test_clearing_slot_preserves_other_slots(resources):
    state=Session(slots={'city':'Dubai','max_budget':300})
    p=QueuedProvider({'intent':'clarify','slots':{'city':None},'question':'Which destination next?'})
    agent(resources,p).respond('Different destination please',state)
    assert state.slots=={'max_budget':300}

def test_arbitrary_long_history_is_available_to_interpreter(resources):
    state=Session(history=[{'role':'user','content':f'turn {i}'} for i in range(100)],slots={'city':'Dubai'})
    p=QueuedProvider({'intent':'query','query':{'operation':'count'}})
    agent(resources,p).respond('How many hotels are in the database?',state)
    assert len(p.calls[0][1]['state']['history'])==100
    assert len(state.history)==102

def test_hard_semantic_requirement_does_not_pass_without_evidence(resources):
    row=next(iter(resources[0].records.values()))
    p=QueuedProvider({'intent':'recommend','query':{'filters':[{'field':'id','op':'eq','value':row['id']}]},
                     'add_preferences':[{'concept':'beach','value':'beachfront','hard':True}]},
                     {'hotels':[{'id':row['id'],'evidence':[]}]})
    out=agent(resources,p).respond('I must have direct beach access',Session())
    assert not out['cards'] and 'no verified match' in out['answer']
    assert 'Missing evidence is unknown' in out['answer']

def test_soft_budget_does_not_exclude_expensive_hotel(resources):
    row=max(resources[0].records.values(),key=lambda r:r['peak_price'])
    p=QueuedProvider({'intent':'recommend','slots':{'max_budget':300,'budget_hard':False},
                     'query':{'filters':[{'field':'id','op':'eq','value':row['id']}]}})
    out=agent(resources,p).respond('Prefer around $300 but can stretch',Session())
    assert out['cards'] and 'exceeds' in out['answer']

def test_unknown_month_uses_higher_rate_for_hard_budget(resources):
    row=next(r for r in resources[0].records.values() if r['peak_price']>r['off_price'] and not r['peak_months'] and not r['off_months'])
    p=QueuedProvider({'intent':'recommend','slots':{'max_budget':row['off_price'],'month':3,'budget_hard':True},
                     'query':{'filters':[{'field':'id','op':'eq','value':row['id']}]}})
    out=agent(resources,p).respond('Hard budget for March',Session())
    assert not out['cards']

def test_estimated_prices_disclosed(resources):
    row=next(r for r in resources[0].records.values() if r['estimated'])
    p=QueuedProvider({'intent':'query','query':{'operation':'detail','ids':[row['id']]}})
    assert 'Estimated reference' in agent(resources,p).respond('Show this hotel',Session())['answer']
