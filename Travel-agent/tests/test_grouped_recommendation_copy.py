"""Common constraints belong in one introduction, not each hotel's selling points."""
from collections import Counter
import pytest
from travel_agent.agent import Agent
from travel_agent.data import Database
from travel_agent.grounding import Grounder
from travel_agent.models import Session, Preference, Evidence
from travel_agent.retrieval import HybridIndex
from test_agent import QueuedProvider

@pytest.fixture(scope='module')
def resources():
    db=Database(); return db,HybridIndex(db)

def test_shared_location_introduced_once_but_still_enforced(resources):
    db,index=resources
    rows=[r for r in db.records.values() if r['city']=='Hongkong'][:3]
    p=QueuedProvider({'intent':'recommend','slots':{'city':'Hongkong'},'query':{'ids':[r['id'] for r in rows]},
                     'add_preferences':[{'concept':'destination','value':'HongKong','target_field':'city',
                                         'normalized_value':'Hongkong','hard':True}]})
    out=Agent(db,index,p).respond('Recommend hotels in Hong Kong',Session())
    introduction=out['answer'].split('###')[0]
    assert '3 stays in **Hongkong, China**' in introduction
    assert out['answer'].count('I found')==1
    for card in out['cards']:
        assert 'in **Hongkong, China**' not in card['text']
        assert '**Hongkong**' not in card['text']
        assert 'on your wish list' not in card['text']
        assert 'I found' not in card['text']
    assert any(f['field']=='city' and f['value']=='Hongkong' for f in out['trace']['query_parameters']['filters'])
    assert all(db.records[c['id']]['city']=='Hongkong' for c in out['cards'])
    assert all(v['weighted_coverage']==1 for v in out['trace']['match_coverage'].values())

def test_geo_evidence_does_not_hide_the_hotel_features(resources):
    db=resources[0]
    row=next(r for r in db.records.values() if r['name']=='Conrad Hong Kong (Hong Kong)')
    pref=Preference(concept='place',value='HongKong',target_field='city',normalized_value='Hongkong')
    evidence=Evidence(preference='place',field='city',quote='Hongkong',relation='hotel_property')
    text=Grounder(db,None).card(row,[evidence],[pref],shared={'city':'Hongkong','country':'China'})
    assert 'Admiralty Core Area' in text and 'Near MTR Station' in text
    assert '**Hongkong**' not in text and 'wish list' not in text
    assert row['name'] in text

def test_hotels_in_different_cities_keep_their_own_city(resources):
    db,index=resources
    japan=[r for r in db.records.values() if r['country']=='Japan']
    first=japan[0]; second=next(r for r in japan if r['city']!=first['city'])
    p=QueuedProvider({'intent':'recommend','requested_count':2,'slots':{'country':'Japan'},
                     'query':{'ids':[first['id'],second['id']]}})
    out=Agent(db,index,p).respond('Compare two stays around Japan',Session())
    assert '2 stays in **Japan**' in out['answer'].split('###')[0]
    for card in out['cards']:
        row=db.records[card['id']]
        assert 'In **'+row['city']+'**.' in card['text']

def test_shared_category_stated_once_in_introduction(resources):
    db,index=resources
    p=QueuedProvider({'intent':'recommend','slots':{'city':'Dubai','category':'Top Luxury'}})
    out=Agent(db,index,p).respond('Luxury hotels in Dubai',Session())
    assert '**Top Luxury** tier' in out['answer'].split('###')[0]
    assert all('tier you’re looking for' not in card['text'] for card in out['cards'])

def test_rare_recorded_features_lead_before_shared_generic_features(resources):
    db=resources[0]; base=next(iter(db.records.values()))
    a=dict(base,labels='Swimming Pool / Courtyard Garden',description='Garden stay.')
    b=dict(base,labels='Swimming Pool / Rooftop Terrace',description='Terrace stay.')
    grounder=Grounder(db,None)
    counts=Counter(grounder.feature_key(v) for row in [a,b] for v in grounder.feature_candidates(row))
    text_a=grounder.card(a,[],[],feature_counts=counts)
    text_b=grounder.card(b,[],[],feature_counts=counts)
    assert text_a.index('Courtyard Garden')<text_a.index('Swimming Pool')
    assert text_b.index('Rooftop Terrace')<text_b.index('Swimming Pool')
    assert 'Rooftop Terrace' not in text_a and 'Courtyard Garden' not in text_b

def test_coverage_diagnostics_can_keep_geographic_evidence_without_sales_repetition(resources):
    db=resources[0]; row=next(iter(db.records.values()))
    geo=Preference(concept='city',value=row['city'],target_field='city',normalized_value=row['city'])
    proof=Grounder(db,None).verify([row],[geo])[row['id']]
    assert proof and Grounder.satisfies(geo,proof)
    text=Grounder(db,None).card(row,proof,[geo],shared={'city':row['city'],'country':row['country']})
    assert 'wish list' not in text and 'I found' not in text
