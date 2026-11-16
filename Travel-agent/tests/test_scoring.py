import pytest
from evaluation.scoring import summarize

def test_official_denominators():
    rows=[{'stage':'completed','scores':{'A':1,'B':1,'C':1},'elapsed_seconds':10},
          {'stage':'completed','scores':{'A':1,'B':0,'C':1},'elapsed_seconds':20},
          {'stage':'interim','scores':{'A':1,'B':None,'C':1},'clarification':True,'elapsed_seconds':46},
          {'stage':'awaiting_review','scores':{'A':None,'B':None,'C':None},'elapsed_seconds':30}]
    r=summarize(rows)
    assert r['completed_scored_cases']==2
    assert r['average_out_of_3']==2.5
    assert r['normalized_percent']==pytest.approx(5/6*100)
    assert r['criterion_pass_percent']['B']==50 and r['perfect_case_percent']==50
    assert r['latency']['clarification_within_45_seconds']==0
    assert r['latency']['p95_nearest_rank']==46

def test_no_fake_scores():
    r=summarize([{'stage':'failed','error':'No model'},{'stage':'awaiting_review','scores':{}}])
    assert r['average_out_of_3'] is None and r['completed_scored_cases']==0

def test_interim_relevance_must_be_na():
    with pytest.raises(ValueError): summarize([{'stage':'interim','scores':{'B':1}}])
