"""Field/state invariants and conversational contracts; no phrase-specific response lookup."""
import pytest
from travel_agent.data import Database
from travel_agent.models import Session, Plan, Preference
from travel_agent.memory import update_search
from travel_agent.retrieval import HybridIndex
from travel_agent.agent import Agent
from test_agent import QueuedProvider

@pytest.fixture(scope='module')
def resources():
    db=Database(); return db,HybridIndex(db)

def test_city_country_reconciliation_for_every_dataset_city(resources):
    db=resources[0]
    locations=sorted({(r['city'],r['country']) for r in db.records.values()})
    for city,country in locations:
        previous=next((c,n) for c,n in locations if n!=country)
        state=Session(slots={'city':previous[0],'country':previous[1]},
                      preferences={'need':Preference(concept='need',value='an independently retained need')})
        update_search(state,Plan(intent='recommend',slots={'city':city}),db)
        assert state.slots['city']==city and state.slots['country']==country
        assert 'need' in state.preferences

def test_country_replacement_for_every_dataset_country(resources):
    db=resources[0]
    for country in {r['country'] for r in db.records.values()}:
        old=next(r for r in db.records.values() if r['country']!=country)
        state=Session(slots={'country':old['country'],'city':old['city']})
        update_search(state,Plan(intent='recommend',slots={'country':country}),db)
        assert state.slots['country']==country and 'city' not in state.slots

def test_category_replacement_is_exclusive_for_all_recorded_tiers(resources):
    categories={r['category'] for r in resources[0].records.values() if r['category']}
    for old in categories:
        for new in categories:
            state=Session(slots={'category':old,'country':'Japan'})
            update_search(state,Plan(intent='recommend',slots={'category':new}),resources[0])
            assert state.slots=={'category':new,'country':'Japan'}

def test_unresolved_meaning_prompts_without_query_or_assumption(resources):
    p=QueuedProvider({'intent':'recommend','slots':{'country':'Japan'},
                     'unresolved_concepts':['a particular atmosphere I cannot interpret']})
    out=Agent(*resources,p).respond('Find that sort of atmosphere',Session())
    assert out['trace']['clarification'] and 'Could you explain' in out['answer']
    assert not out['cards'] and len(p.calls)==1

def test_tentative_interpretation_is_not_assumed(resources):
    p=QueuedProvider({'intent':'recommend','slots':{'country':'Japan'},
                     'add_preferences':[{'concept':'experience','value':'seclusion',
                                         'confidence':0.4,'confirmed':False}]})
    out=Agent(*resources,p).respond('Somewhere I can disconnect',Session())
    assert out['trace']['clarification'] and 'what would that look like' in out['answer']
    assert len(p.calls)==1

def test_no_matching_soft_evidence_does_not_generate_random_shortlist(resources):
    row=next(iter(resources[0].records.values()))
    p=QueuedProvider({'intent':'recommend','query':{'ids':[row['id']]},
                     'add_preferences':[{'concept':'specific_need','value':'explicit unusual experience'}]},
                    {'hotels':[]})
    out=Agent(*resources,p).respond('I want this specific experience',Session())
    assert out['trace']['clarification'] and not out['cards']
    assert 'couldn’t verify a match' in out['answer']
    assert out['trace']['match_coverage'][row['id']]['weighted_coverage']==0

def test_brand_is_persistent_and_applied_as_structured_filter(resources):
    p=QueuedProvider({'intent':'recommend','slots':{'country':'Japan','brand':'Hyatt'}},
                     {'intent':'recommend','slots':{'max_budget':1000}})
    state=Session(); a=Agent(*resources,p)
    a.respond('A Hyatt hotel in Japan',state)
    out=a.respond('My nightly ceiling is $1000',state)
    assert state.slots['brand']=='Hyatt'
    assert all('hyatt' in resources[0].records[c['id']]['brand'].casefold() for c in out['cards'])
    assert any(f['field']=='brand' for f in out['trace']['query_parameters']['filters'])

def test_only_user_closing_intent_pauses_and_later_question_resumes(resources):
    p=QueuedProvider({'intent':'recommend','slots':{'country':'Japan'}},
                     {'intent':'close'},
                     {'intent':'query','references':[1],'query':{'operation':'detail'},'requested_fields':['peak_months']})
    state=Session(); a=Agent(*resources,p)
    a.respond('Some options in Japan',state)
    assert state.status=='active'
    ids=list(state.last_ids); prefs=state.slots.copy(); result=state.last_result.copy()
    out=a.respond('That is all I need, thank you',state)
    assert state.status=='paused' and not out['cards']
    assert state.last_ids==ids and state.slots==prefs and state.last_result==result
    assert len(p.calls)==2  # Closing makes no retrieval/evidence calls.
    out=a.respond('One more thing: peak season for the first one?',state)
    assert state.status=='active' and out['trace']['retrieved_ids']==[ids[0]]
    assert len(state.history)==6

def test_thanks_with_a_remaining_question_is_not_forced_to_close(resources):
    # No code scans for 'thanks': the semantic intent still controls the route.
    p=QueuedProvider({'intent':'query','query':{'operation':'count'}})
    state=Session()
    out=Agent(*resources,p).respond('Thanks; how many hotels are in your data?',state)
    assert state.status=='active' and '622' in out['answer']

def test_missing_location_asks_and_exploration_can_skip(resources):
    p=QueuedProvider({'intent':'recommend'},
                     {'intent':'recommend','slots':{'exploratory':True}})
    state=Session(); a=Agent(*resources,p)
    first=a.respond('I would like a hotel',state)
    assert first['trace']['clarification'] and state.pending_topic=='destination'
    second=a.respond('Suggest destinations too; surprise me',state)
    assert second['cards'] and not second['trace']['clarification']
