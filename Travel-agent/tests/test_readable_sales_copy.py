"""Presentation regressions: readable punctuation and grounded consultant-style copy."""
import pytest
from travel_agent.data import Database
from travel_agent.grounding import Grounder
from travel_agent.models import Query, Preference, Evidence
from travel_agent.responses import render_query

@pytest.fixture(scope='module')
def db(): return Database()

def test_apostrophe_is_not_turned_into_a_literal_html_entity():
    assert Grounder.safe_text("Manhattan's Flatiron District")=="Manhattan's Flatiron District"
    assert Grounder.safe_text('Manhattan&#x27;s Flatiron District')=="Manhattan's Flatiron District"
    assert Grounder.safe_text('"A hotel"')=='"A hotel"'

def test_markdown_controls_and_html_stay_inert():
    text=Grounder.safe_text('<script>alert("x")</script> [click](javascript:alert(1)) **fake** $300 | room')
    assert '<script>' not in text
    assert '&lt;script&gt;' in text
    assert '\\[click\\]' in text and '\\*\\*fake\\*\\*' in text
    assert '\\$300' in text and '\\|' in text

def test_actual_edition_description_reads_normally(db):
    row=next(r for r in db.records.values() if r['name']=='The New York Edition Hotel')
    q=Query(operation='detail',ids=[row['id']])
    text=render_query(db.query(q),q,['description'],'Reference rates only.')
    assert "Manhattan's Flatiron District" in text
    assert '&#x27;' not in text and '&\\#x27;' not in text
    assert '1909' in text and 'Madison Square Park' in text

def test_card_starts_with_hotel_features_without_a_repeated_sales_introduction(db):
    row=next(r for r in db.records.values() if r['name']=='Raffles Dubai Palm Hotel')
    text=Grounder(db,None).card(row,[],[],search={'category':'Top Luxury'})
    assert f"### {row['name']}" in text
    assert "I found" not in text
    assert 'The appeal here is' in text
    assert 'Why I’d shortlist' not in text and 'for your preference for' not in text
    for field in ('off_price','peak_price'):
        assert f"USD {row[field]:,.2f}" in text
    assert 'Private Beach' in row['labels'] and 'Private Beach' in text
    assert 'guaranteed' not in text.lower() and 'best deal' not in text.lower()

def test_personalized_sales_reason_keeps_the_verified_quote(db):
    row=next(r for r in db.records.values() if 'Swimming Pool' in r['labels'])
    p=Preference(concept='pool',value='a swimming pool',hard=True)
    e=Evidence(preference='pool',field='labels',quote='Swimming Pool',supports=True,relation='hotel_property')
    text=Grounder(db,None).card(row,[e],[p])
    assert 'The appeal here is' in text
    assert '**Swimming Pool**' in text
    assert 'on your wish list' not in text
    assert 'the reason' not in text.lower()

def test_estimate_and_budget_caveats_survive_warmer_copy(db):
    row=next(r for r in db.records.values() if r['estimated'])
    text=Grounder(db,None).card(row,[],[],budget=1)
    assert 'estimated reference rates' in text
    assert 'marked as estimates' in text and 'exceeds' in text
    assert 'confirmed rates' in text
