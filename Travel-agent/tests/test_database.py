import pytest
from pydantic import ValidationError
from travel_agent.data import Database
from travel_agent.models import Query, Filter

@pytest.fixture(scope='module')
def db(): return Database()

def test_actual_schema_and_keys(db):
    assert len(db.records)==622
    assert len({(r['country'],r['city'],r['name']) for r in db.records.values()})==622
    assert sum(r['estimated'] for r in db.records.values())==1

def test_count_and_aggregates(db):
    expected=[r for r in db.records.values() if r['city']=='Dubai']
    q=Query(filters=[Filter(field='city',op='eq',value='dubai')],operation='mean',price_field='peak_price')
    result=db.query(q)
    assert result['count']==len(expected)>0
    assert result['mean']==pytest.approx(sum(r['peak_price'] for r in expected)/len(expected))
    assert db.query(Query(operation='count'))['count']==622

def test_group(db):
    r=db.query(Query(operation='group',group_by='brand'))
    assert sum(g['count'] for g in r['groups'])==622

def test_unknown_and_injection(db):
    with pytest.raises(ValidationError): Query(filters=[{'field':'name; DROP TABLE hotels','value':'x'}])
    assert db.query(Query(filters=[Filter(field='name',value="' OR 1=1 --")]))['count']==0
    with pytest.raises(Exception): db.conn.execute('DELETE FROM hotels')

def test_sort_and_comparison_order(db):
    rows=db.query(Query(price_field='peak_price',limit=20))['rows']
    assert [r['peak_price'] for r in rows]==sorted(r['peak_price'] for r in rows)
    ids=[rows[3]['id'],rows[0]['id']]
    assert [r['id'] for r in db.query(Query(operation='compare',ids=ids))['rows']]==ids

def test_season_unknown_is_conservative(db):
    row=next(r for r in db.records.values() if not r['peak_months'] and not r['off_months'])
    assert db.price(row,3)==(max(row['peak_price'],row['off_price']),'unknown')
    custom=dict(row,peak_months='June, July',off_months='January')
    assert db.price(custom,6)==(row['peak_price'],'peak')
    assert db.price(custom,1)==(row['off_price'],'off')
    assert db.price(custom,3)[1]=='unknown'

def test_all_candidates(db):
    assert len(db.candidates(Query()))==622
    assert all(r['city']=='Abu Dhabi' for r in db.candidates(Query(filters=[Filter(field='city',op='eq',value='Abu Dhabi')])))

def test_seasonal_difference(db):
    row=next(iter(db.records.values()))
    result=db.query(Query(operation='seasonal',ids=[row['id']]))['seasonal'][0]
    assert result['difference_usd']==row['peak_price']-row['off_price']
    assert result['change_percent']==pytest.approx((row['peak_price']/row['off_price']-1)*100)
