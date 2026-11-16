import pytest
from travel_agent.data import Database
from travel_agent.retrieval import HybridIndex
from travel_agent.models import Query, Filter

@pytest.fixture(scope='module')
def resources():
    db=Database(); return db, HybridIndex(db)

def test_ranking_uses_filtered_pool(resources):
    db,index=resources
    candidates=db.candidates(Query(filters=[Filter(field='city',op='eq',value='Abu Dhabi')]))
    ranked=index.rank('beach ocean views resort',candidates)
    assert len(ranked)==len(candidates)>0
    assert all(r['city']=='Abu Dhabi' for r in ranked)
    assert any('beach' in (r['labels']+r['description']).lower() for r in ranked[:5])

def test_semantic_signal_is_not_proof(resources):
    db,index=resources
    row=next(iter(db.records.values()))
    assert index.rank('all inclusive volcano ice castle',[row])[0]==row
    # Ranking returns candidates; evidence verification is a separate gate.

def test_empty_pool(resources):
    assert resources[1].rank('anything',[])==[]
