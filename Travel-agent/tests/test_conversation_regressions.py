"""Reported conversational failures: deterministic plan/tool contracts, not paid model evaluation."""
import pytest
from travel_agent.agent import Agent
from travel_agent.data import Database
from travel_agent.models import Session, Preference, Query
from travel_agent.retrieval import HybridIndex
from test_agent import QueuedProvider

@pytest.fixture(scope='module')
def resources():
    db=Database()
    return db, HybridIndex(db)

def test_japan_high_end_to_dubai_luxury_replaces_both_constraints(resources):
    db,index=resources
    provider=QueuedProvider(
        {'intent':'recommend','slots':{'country':'Japan','category':'high-end'}},
        {'intent':'recommend','slots':{'city':'Dubai','category':'Top Luxury'},
         # Even a stale tier/location tool filter must not override the current slots.
         'query':{'limit':1,'filters':[{'field':'category','op':'eq','value':'high-end'},
                                     {'field':'country','op':'eq','value':'Japan'}]}})
    state=Session()
    agent=Agent(db,index,provider)
    first=agent.respond('High end hotel in Japan',state)
    assert len(first['cards'])==3
    assert all(db.records[c['id']]['country']=='Japan' and db.records[c['id']]['category']=='high-end' for c in first['cards'])
    second=agent.respond('Luxury hotel in Dubai',state)
    assert state.slots['country']=='UAE' and state.slots['city']=='Dubai'
    assert state.slots['category']=='Top Luxury'
    assert len(second['cards'])==2  # Actual source has exactly two Top Luxury hotels in Dubai.
    assert all(db.records[c['id']]['city']=='Dubai' and db.records[c['id']]['category']=='Top Luxury' for c in second['cards'])
    assert 'closest checked matches' in second['answer']
    assert 'Why' not in second['answer'] or 'record says' not in second['answer']
    assert 'I found 2 stays in **Dubai, UAE**' in second['answer']
    assert 'The appeal here is' in second['answer']

def test_low_budget_clarifies_even_if_planner_intent_is_recommend(resources):
    db,index=resources
    p=QueuedProvider({'intent':'recommend','slots':{'budget_kind':'subjective','budget_description':'low'}})
    state=Session(slots={'city':'Dubai','country':'UAE','max_budget':500,'budget_hard':False})
    out=Agent(db,index,p).respond('My budget is low',state)
    assert out['trace']['clarification'] and out['trace']['intent']=='clarify'
    assert 'nightly budget in USD' in out['answer'] and not out['cards']
    assert 'max_budget' not in state.slots and state.pending_topic=='budget'
    assert state.slots['city']=='Dubai'
    p.responses.append({'intent':'recommend','slots':{'max_budget':300}})
    out=Agent(db,index,p).respond('No more than $300 per night',state)
    assert not out['trace']['clarification']
    assert state.slots['budget_kind']=='numeric' and state.slots['budget_hard']
    assert all(db.price(db.records[c['id']])[0]<=300 for c in out['cards'])

def test_skipping_budget_does_not_repeat_question(resources):
    db,index=resources
    state=Session(slots={'city':'Dubai','budget_kind':'subjective'},pending_topic='budget')
    p=QueuedProvider({'intent':'recommend','slots':{'budget_kind':'skipped'}})
    out=Agent(db,index,p).respond('Just show options; no fixed budget',state)
    assert out['cards'] and not out['trace']['clarification']
    assert state.pending_question is None

def test_peak_month_question_is_direct_qa_and_preserves_search(resources):
    db,index=resources
    row=next(r for r in db.records.values() if r['name']=='Raffles Dubai Palm Hotel')
    p=QueuedProvider({'intent':'query','query':{'operation':'detail','filters':[{'field':'name','op':'eq','value':row['name']}]},
                     'requested_fields':['peak_months']})
    state=Session(slots={'country':'Japan','category':'high-end','budget_kind':'subjective'})
    out=Agent(db,index,p).respond('When is peak season for Raffles Dubai Palm Hotel?',state)
    assert row['peak_months'] in out['answer']
    assert 'Peak-season months' in out['answer']
    assert 'nightly budget' not in out['answer'] and not out['trace']['clarification']
    assert 'Reference rates' not in out['answer'] and '```json' not in out['answer']
    assert state.slots['country']=='Japan'
    catalog=p.calls[0][1]['hotel_candidates']
    assert any(c['id']==row['id'] for c in catalog)

def test_missing_peak_months_is_unknown_not_sampling_date(resources):
    db,index=resources
    row=next(r for r in db.records.values() if not r['peak_months'])
    p=QueuedProvider({'intent':'query','query':{'operation':'detail','ids':[row['id']]},'requested_fields':['peak_months']})
    out=Agent(db,index,p).respond('What is its peak season?',Session())
    assert 'not recorded' in out['answer'] and 'can’t confirm' in out['answer']

def test_question_feature_does_not_become_a_permanent_preference(resources):
    db,index=resources
    row=next(iter(db.records.values()))
    p=QueuedProvider({'intent':'query','query':{'operation':'detail','ids':[row['id']]},
                     'add_preferences':[{'concept':'pool','value':'swimming pool'}],
                     'requested_fields':['labels']}, {'hotels':[]})
    state=Session(preferences={'family':Preference(concept='family',value='family trip')})
    Agent(db,index,p).respond('Does this hotel have a pool?',state)
    assert set(state.preferences)=={'family'}

def test_country_change_clears_incompatible_city(resources):
    db,index=resources
    state=Session(slots={'city':'Dubai','country':'UAE'})
    p=QueuedProvider({'intent':'recommend','slots':{'country':'Japan','category':'high-end'}})
    out=Agent(db,index,p).respond('Instead, high-end hotels in Japan',state)
    assert 'city' not in state.slots
    assert all(db.records[c['id']]['country']=='Japan' for c in out['cards'])

def test_explicit_replacement_and_dimensions_do_not_accumulate(resources):
    from travel_agent.memory import update_search
    from travel_agent.models import Plan
    state=Session(preferences={'old_style':Preference(concept='old_style',value='traditional',dimension='decor'),
                              'family':Preference(concept='family',value='family')})
    update_search(state,Plan(intent='recommend',add_preferences=[Preference(concept='new_style',value='modern',dimension='decor')]),resources[0])
    assert set(state.preferences)=={'new_style','family'}

def test_multiple_database_questions_run_all_tools_and_render_prose(resources):
    db,index=resources
    filters=[{'field':'city','op':'eq','value':'Dubai'}]
    p=QueuedProvider({'intent':'query','query':{'operation':'count','filters':filters},
                     'additional_queries':[{'operation':'mean','price_field':'peak_price','filters':filters}]})
    out=Agent(db,index,p).respond('How many Dubai hotels are there and what is their average peak price?',Session())
    expected=[r for r in db.records.values() if r['city']=='Dubai']
    mean=sum(r['peak_price'] for r in expected)/len(expected)
    assert '4 hotel records' in out['answer'] and f'USD {mean:,.2f}' in out['answer']
    assert out['trace']['selected_tools']==['count','mean']
    assert '```' not in out['answer']

def test_ambiguous_hotel_name_asks_which_instead_of_choosing_cheapest(resources):
    db,index=resources
    p=QueuedProvider({'intent':'query','query':{'operation':'detail','filters':[{'field':'name','value':'Hyatt'}]},
                     'requested_fields':['peak_months']})
    out=Agent(db,index,p).respond('When is peak season for the Hyatt?',Session())
    assert out['trace']['clarification'] and 'Which hotel did you mean' in out['answer']
    assert out['trace']['result']['matching_count']>1

def test_explicit_question_need_asks_before_search(resources):
    db,index=resources
    p=QueuedProvider({'intent':'recommend','clarification_needs':[
        {'topic':'experience','question':'What does relaxing look like for you?','priority':5},
        {'topic':'budget','question':'What budget?','priority':3}]})
    out=Agent(db,index,p).respond('A place to do nothing',Session())
    assert out['answer']=='What does relaxing look like for you?'
    assert len(p.calls)==1 and out['trace']['clarification']

def test_requested_count_is_distinct_from_qa_limit(resources):
    db,index=resources
    p=QueuedProvider({'intent':'recommend','slots':{'country':'Japan'},'requested_count':1,'query':{'limit':10}})
    out=Agent(db,index,p).respond('Pick just one hotel in Japan',Session())
    assert len(out['cards'])==1

def test_reply_to_ambiguous_hotel_question_resolves_pending_choices(resources):
    db,index=resources
    old_ids=[r['id'] for r in db.records.values() if r['city']=='Dubai'][:3]
    state=Session(last_ids=old_ids)
    p=QueuedProvider({'intent':'query','query':{'operation':'detail','filters':[{'field':'name','value':'Hyatt'}]},
                     'requested_fields':['peak_months']},
                    {'intent':'query','references':[1],'query':{'operation':'detail'},'requested_fields':['peak_months']})
    a=Agent(db,index,p)
    a.respond('When is peak season for the Hyatt?',state)
    pending=state.pending_ids[0]
    assert state.pending_topic=='hotel_reference'
    out=a.respond('The first of those choices',state)
    assert out['trace']['retrieved_ids']==[pending]
    assert state.focus_ids==[pending] and state.last_ids==old_ids
    assert not state.pending_ids and state.pending_topic is None
