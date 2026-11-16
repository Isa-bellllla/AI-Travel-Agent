"""Rubric A/B: correct field and subject. Rubric C: use the clarification answer."""
import pytest
from travel_agent.agent import Agent
from travel_agent.data import Database
from travel_agent.grounding import Grounder
from travel_agent.models import Preference, Session, ClarificationNeed, Plan
from travel_agent.retrieval import HybridIndex
from travel_agent.memory import clarification, update_search
from test_agent import QueuedProvider

@pytest.fixture(scope='module')
def resources():
    db=Database(); return db,HybridIndex(db)

def test_luxury_tier_never_uses_nearby_luxury_words(resources):
    db=resources[0]
    row=dict(next(iter(db.records.values())),category='high-end',labels='Luxury resort nearby',
             description='Across the street from a luxury resort.',brand='ordinary brand')
    p=QueuedProvider()  # No LLM permission to reinterpret a structured category value.
    preference=Preference(concept='tier',value='luxury hotel',target_field='category',normalized_value='Top Luxury',hard=True)
    evidence=Grounder(db,p).verify([row],[preference])[row['id']]
    assert not Grounder.satisfies(preference,evidence)
    assert evidence[0].field=='category' and evidence[0].quote=='high-end'
    assert evidence[0].supports is False and not p.calls

def test_correct_tier_needs_no_luxury_word_in_description(resources):
    db=resources[0]
    row=dict(next(iter(db.records.values())),category='Top Luxury',labels='Central location',description='A city hotel.')
    p=QueuedProvider()
    preference=Preference(concept='tier',value='luxury hotel',target_field='category',normalized_value='Top Luxury')
    evidence=Grounder(db,p).verify([row],[preference])[row['id']]
    assert Grounder.satisfies(preference,evidence)
    assert evidence[0].field=='category' and not p.calls

def test_brand_mention_in_description_does_not_establish_brand(resources):
    db=resources[0]
    row=dict(next(iter(db.records.values())),brand='Sofitel',description='Near a Hyatt hotel.')
    p=QueuedProvider()
    preference=Preference(concept='brand',value='Hyatt',target_field='brand',normalized_value='Hyatt')
    evidence=Grounder(db,p).verify([row],[preference])[row['id']]
    assert not Grounder.satisfies(preference,evidence)
    assert evidence[0].quote=='Sofitel' and not p.calls

def test_unmapped_category_never_falls_back_to_labels(resources):
    db=resources[0]; row=dict(next(iter(db.records.values())),labels='luxury brand')
    p=QueuedProvider()
    pref=Preference(concept='tier',value='luxury brand',target_field='category')
    assert Grounder(db,p).verify([row],[pref])[row['id']]==[]
    state=Session(slots={'city':'Dubai'},preferences={'tier':pref})
    question,topic=clarification(Plan(intent='recommend'),state)
    assert topic=='category' and 'Top Luxury' in question

def test_other_entity_pool_does_not_establish_hotel_pool(resources):
    db=resources[0]
    row=dict(next(iter(db.records.values())),description='The neighboring resort has a swimming pool.')
    p=QueuedProvider({'hotels':[{'id':row['id'],'evidence':[
        {'preference':'pool','field':'description','quote':row['description'],
         'supports':True,'relation':'other_entity'}]}]})
    preference=Preference(concept='pool',value='swimming pool',hard=True)
    evidence=Grounder(db,p).verify([row],[preference])[row['id']]
    assert not evidence and not Grounder.satisfies(preference,evidence)

def test_proximity_is_valid_only_for_a_proximity_preference(resources):
    db=resources[0]
    row=dict(next(iter(db.records.values())),labels='Close to a waterfront promenade')
    p=QueuedProvider({'hotels':[{'id':row['id'],'evidence':[
        {'preference':'location','field':'labels','quote':row['labels'],
         'supports':True,'relation':'hotel_location_relation'}]}]})
    pref=Preference(concept='location',value='near a promenade',evidence_scope='proximity')
    assert Grounder.satisfies(pref,Grounder(db,p).verify([row],[pref])[row['id']])

def test_category_answer_resolves_old_uncertainty_and_stale_repeat(resources):
    db,index=resources
    question='Which recorded accommodation tier do you mean?'
    need={'topic':'category','target_slot':'category','preference_keys':['tier_uncertain'],
          'question':question,'reason':'ambiguous'}
    p=QueuedProvider(
        {'intent':'clarify','slots':{'city':'Dubai'},'clarification_needs':[need],
         'add_preferences':[{'concept':'tier_uncertain','value':'luxury or chain tier',
                             'target_field':'category','confirmed':False,'confidence':0.4}]},
        # Deliberately leave stale clarification output: the engine must use the answer anyway.
        {'intent':'clarify','slots':{'category':'Top Luxury'},'clarification_needs':[need],
         'question':question,'question_topic':'category','resolved_topics':['category']},
        {'intent':'query','references':[1,2],'query':{'operation':'list','price_field':'peak_price','limit':1}})
    state=Session(); a=Agent(db,index,p)
    first=a.respond('I want a luxury hotel in Dubai',state)
    assert first['trace']['clarification']
    assert state.clarification_memory['category'].status=='pending'
    second=a.respond('I mean the luxury hotel tier, not a particular chain',state)
    assert not second['trace']['clarification']
    assert len(second['cards'])==2
    assert all(db.records[c['id']]['category']=='Top Luxury' for c in second['cards'])
    assert 'tier_uncertain' not in state.preferences
    record=state.clarification_memory['category']
    assert record.status=='answered' and record.values=={'category':'Top Luxury'}
    assert record.answer=='I mean the luxury hotel tier, not a particular chain'
    assert record.source_turn==1 and record.resolved_turn==2
    latest=list(state.last_ids)
    third=a.respond('Which of those is cheapest in peak season?',state)
    expected=min(latest,key=lambda i:(db.records[i]['peak_price'],i))
    assert third['trace']['retrieved_ids']==[expected]
    assert state.slots['city']=='Dubai' and state.slots['category']=='Top Luxury'
    assert len(state.history)==6

def test_resolved_category_with_no_destination_asks_only_destination(resources):
    db,index=resources
    need={'topic':'category','target_slot':'category','question':'Which hotel tier?','reason':'ambiguous'}
    p=QueuedProvider({'intent':'clarify','clarification_needs':[need]},
                     {'intent':'clarify','slots':{'category':'Top Luxury'},'question':'Which hotel tier?',
                      'question_topic':'category','clarification_needs':[need]})
    state=Session(); a=Agent(db,index,p)
    a.respond('A particular tier',state)
    result=a.respond('The luxury tier is fine',state)
    assert result['trace']['clarification'] and state.pending_topic=='destination'
    assert 'country or city' in result['answer'] and 'Which hotel tier?' not in result['answer']
    assert state.clarification_memory['category'].status=='answered'

def test_confirmed_semantic_interpretation_clears_uncertainty(resources):
    db,index=resources
    row=next(r for r in db.records.values() if 'Swimming Pool' in r['labels'])
    need={'topic':'pool_meaning','preference_keys':['pool'],'question':'Do you mean a hotel with its own swimming pool?'}
    p=QueuedProvider({'intent':'clarify','query':{'ids':[row['id']]},'clarification_needs':[need],
                     'add_preferences':[{'concept':'pool','value':'swimming pool','confirmed':False,'confidence':0.5}]},
                     {'intent':'recommend','query':{'ids':[row['id']]},'confirmed_preferences':['pool'],
                      'resolved_topics':['pool_meaning']},
                     {'hotels':[{'id':row['id'],'evidence':[{'preference':'pool','field':'labels','quote':'Swimming Pool',
                        'supports':True,'relation':'hotel_property'}]}]})
    state=Session(); a=Agent(db,index,p)
    a.respond('I want that kind of pool',state)
    result=a.respond('Yes, its own swimming pool',state)
    assert result['cards'] and not result['trace']['clarification']
    assert state.preferences['pool'].confirmed and state.preferences['pool'].confidence==1
    assert state.clarification_memory['pool_meaning'].status=='answered'

def test_new_conflict_can_be_clarified_after_old_answer(resources):
    from travel_agent.models import ClarificationRecord
    state=Session(slots={'category':'Top Luxury'},clarification_memory={
        'category':ClarificationRecord(question='Tier?',source_turn=1,status='answered',values={'category':'Top Luxury'})})
    plan=Plan(intent='recommend',clarification_needs=[ClarificationNeed(topic='category',target_slot='category',
        question='These two tier requirements conflict; which should apply?',reason='conflict')])
    assert clarification(plan,state)[0]==plan.clarification_needs[0].question

def test_cleared_answer_does_not_remain_falsely_resolved(resources):
    from travel_agent.models import ClarificationRecord
    state=Session(slots={'city':'Dubai','category':'Top Luxury'},clarification_memory={
        'category':ClarificationRecord(question='Tier?',source_turn=1,status='answered',values={'category':'Top Luxury'})})
    plan=Plan(intent='clarify',slots={'category':None},question='Which tier now?',question_topic='category')
    update_search(state,plan,resources[0])
    assert clarification(plan,state)==('Which tier now?','category')

@pytest.mark.parametrize('field,desired,actual',[
    ('category','Top Luxury','high-end'),('brand','Hyatt','Sofitel'),
    ('city','Dubai','Tokyo'),('country','Japan','UAE')])
def test_all_structured_fields_ignore_other_field_word_coverage(resources,field,desired,actual):
    db=resources[0]; row=dict(next(iter(db.records.values())))
    row.update(labels=desired,description=desired,benefits=desired)
    row[field]=actual
    pref=Preference(concept='requirement',value=desired,target_field=field,normalized_value=desired)
    p=QueuedProvider()
    evidence=Grounder(db,p).verify([row],[pref])[row['id']]
    assert len(evidence)==1 and evidence[0].field==field
    assert not Grounder.satisfies(pref,evidence) and not p.calls

def test_resolution_survives_different_topic_names_for_the_same_field(resources):
    from travel_agent.models import ClarificationRecord
    state=Session(slots={'city':'Dubai','category':'Top Luxury'},clarification_memory={
        'brand_level':ClarificationRecord(question='Tier?',source_turn=1,status='answered',
                                         target_slot='category',values={'category':'Top Luxury'})})
    plan=Plan(intent='recommend',clarification_needs=[ClarificationNeed(topic='accommodation_level',
        question='Tier again?',target_slot='category',reason='ambiguous')])
    assert clarification(plan,state)==(None,None)

def test_automatic_uncertainty_question_remembers_the_preference_key(resources):
    db,index=resources
    p=QueuedProvider({'intent':'recommend','slots':{'city':'Dubai'},
                     'add_preferences':[{'concept':'experience','value':'a restful atmosphere','confirmed':False}]})
    state=Session(); Agent(db,index,p).respond('A restful feeling',state)
    assert state.clarification_memory['experience'].preference_keys==['experience']
