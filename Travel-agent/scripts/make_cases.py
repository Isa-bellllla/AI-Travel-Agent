"""Frozen annotations. Held-out prompts must not be used for prompt tuning."""
import json
from pathlib import Path

def case(i,split,turns,concepts,hard=(),expected='Use grounded tools; human-review A/B/C'):
 return {'id':i,'split':split,'turns':turns,'annotation':{
  'expected_concepts':concepts,'hard_constraints':list(hard),'expected_behavior':expected,
  'follow_up_answers_frozen':True,'rubric_scores':'Human review required; no model-based auto-pass'}}

cases=[
 case('dev_clear','development',['A luxury hotel in Abu Dhabi with ocean views, please.'],['Abu Dhabi','luxury','ocean views'],['Abu Dhabi'], 'Proceed directly; ocean evidence must be explicit.'),
 case('dev_constraints','development',['I must stay in Dubai, under $300 per night, and need a swimming pool.'],['Dubai','USD 300 ceiling','swimming pool'],['Dubai','budget','pool']),
 case('dev_subjective_budget','development',['Somewhere nice but not too expensive.','Let’s say Dubai, no more than $250 a night.'],['subjective budget','Dubai','USD 250 ceiling'],['Dubai','budget'],'Clarify essential destination/budget; never invent a numeric amount.'),
 case('dev_quiet','development',['I need somewhere quiet in Dubai.','I mean a room away from street noise, not a remote resort.'],['Dubai','quiet room','not necessarily remote'],['Dubai'],'Clarify materially distinct quiet experiences, preserve answer; do not infer soundproofing.'),
 case('dev_no_match','development',['A hotel in Dubai costing no more than $1 per night.'],['Dubai','USD 1 maximum'],['Dubai','budget'],'No structured matches; ask what to relax.'),
 case('dev_brand_average','development',['What is the mean off-season nightly price of Hyatt hotels in the database?'],['Hyatt brand text','mean','off-season'],'', 'Execute aggregate, explain brand substring scope and estimated rates.'),
 case('dev_season','development',['Which Dubai hotel has the lowest peak-season reference rate?'],['Dubai','lowest','peak-season'],['Dubai'],'Sort structured prices, show actual cheapest record.'),
 case('dev_update','development',['Dubai with my family; a luxury hotel with a pool and access to attractions.','Actually I don’t need a pool anymore. Downtown access is more important.'],['Dubai','family','luxury','remove pool','priority downtown'],['Dubai'],'Remove pool requirement without creating anti-pool constraint; preserve unrelated context.'),
 case('dev_explore','development',['Surprise me with somewhere beautiful.'],['open-ended exploration'],[], 'Proceed with grounded options without imposing invented location/budget.'),
 case('dev_availability','development',['Can you guarantee a room next Friday?'],['availability guarantee'],[],'Explain lack of live availability; never promise a room.'),
 case('dev_conflict','development',['I must be in both Dubai and Paris for the same hotel stay.'],['Dubai','Paris','conflicting destination'],[],'Ask a targeted clarification rather than silently selecting one destination.'),
 case('dev_similar','development',['Show me three hotels in Abu Dhabi.','Tell me about the second one.','Find something similar but cheaper.'],['Abu Dhabi','second reference','similar','cheaper'],['Abu Dhabi','lower recorded rate'],'Use latest list, focus reference, strict cheaper tool condition.'),
 case('holdout_unseen','held_out',['My idea of unwinding is watching the sea rather than booking treatments. Any stays in Muscat that fit?'],['Muscat','sea','relaxation without assumed spa'],['Muscat']),
 case('holdout_urban_quiet','held_out',['I like the bustle outside, but want a restful base in Buenos Aires.'],['Buenos Aires','urban access','restful'],['Buenos Aires'],'Do not conflate restful with rural/remote.'),
 case('holdout_group','held_out',['Count the hotel records by city.'],['count','group city'],[], 'Run whole-dataset grouped count; no recommendation pipeline.'),
 case('holdout_seasonal_delta','held_out',['Show me the first three hotels in Paris, cheapest off-season first.','How much do their prices rise in peak season, in dollars and percent?'],['Paris','sort off-season','seasonal differences','previous records'],['Paris'],'Compute deterministic seasonal differences for the same IDs.'),
 case('holdout_negation','held_out',['I must avoid resorts in Dubai.'],['Dubai','exclude resorts'],['Dubai','not resort'],'Require explicit negative evidence; unknown is not proof.'),
 case('holdout_month','held_out',['I’m going to Muscat in July, budget $400 per night.'],['Muscat','July','USD 400'],['Muscat','budget'],'Use explicit recorded months; conservative higher rate if unknown.'),
 case('holdout_comparison','held_out',['Pick three hotels in Tokyo.','Compare the first and third.','Which is cheaper off-season?'],['Tokyo','first and third','cheapest off-season'],['Tokyo'],'Reuse ordered list and comparison focus; avoid new search.'),
 case('holdout_long_memory','held_out',['Dubai for my family.','A pool is a must.','A central location would help.','Budget up to $350.','Actually remove the pool requirement.','Keep the family and central location preferences.','I can stretch the budget; it isn’t a hard limit.','What was the second option?'],['Dubai','family','central','pool removed','flexible budget','second reference'],['Dubai'],'Maintain cumulative state; remove only obsolete pool; do not invent new budget.'),
 case('holdout_sparse_data','held_out',['Which of your hotels has guaranteed soundproof rooms and a measured 300-metre walk to a train station?'],['soundproof guarantee','measured distance'],[],'Explain unsupported detail; no inferred measurements.'),
 case('holdout_brand','held_out',['How many hotels have no recorded brand, and what is their average peak-season rate?'],['blank brand','count','mean peak-season'],[],'Use empty-string equality filter and deterministic aggregation; no inferred brand.'),
 case('acceptance_10_turn','acceptance',[
  'I want a hotel where I can just relax and do nothing.',
  "I’d love to be somewhere near the beach.", 'Abu Dhabi would be nice.',
  "I don’t want anything too expensive.", 'Under $300 per night.',
  'Which of those is the cheapest during peak season?',
  'Actually, I can spend a little more if the hotel is better.',
  'Tell me more about the second one.', 'Does it have a swimming pool?',
  'Find something similar but cheaper.'
 ],['relaxation','beach','Abu Dhabi','subjective then numeric budget','peak comparison','budget flexibility','second reference','pool inquiry','similar cheaper'],['Abu Dhabi','USD 300 until relaxed'], 'Evaluate final case cumulatively after predefined follow-ups, with A/B/C evidence. Clarification initial B=N/A.')
]
cases.extend([{'id': 'reported_destination_tier_change', 'split': 'regression', 'turns': ['High end hotel in Japan', 'Luxury hotel in Dubai'], 'annotation': {'expected_concepts': ['Japan then Dubai', 'high-end replaced by Top Luxury'], 'hard_constraints': ['latest destination Dubai', 'latest category Top Luxury'], 'expected_behavior': 'Replace incompatible slots; return the two Top Luxury Dubai source records if no further constraints apply; do not carry one-result limit.', 'follow_up_answers_frozen': True}}, {'id': 'reported_low_budget', 'split': 'regression', 'turns': ['Recommend hotels in Dubai', 'My budget is low', 'No more than $300 per night'], 'annotation': {'expected_concepts': ['Dubai', 'subjective budget', 'USD 300 numeric ceiling'], 'hard_constraints': ['Dubai', 'USD 300 after clarification'], 'expected_behavior': 'Ask a focused budget question without inventing dollars, then apply the answer and preserve Dubai.', 'follow_up_answers_frozen': True}}, {'id': 'reported_peak_months', 'split': 'regression', 'turns': ['When is peak season for Raffles Dubai Palm Hotel?'], 'annotation': {'expected_concepts': ['named hotel', 'peak-season timing'], 'hard_constraints': ['correct hotel record'], 'expected_behavior': 'Direct detail lookup; June, July, August, September; no budget clarification and no invented live availability.', 'follow_up_answers_frozen': True}}])
Path('evaluation/cases.json').write_text(json.dumps(cases,indent=2,ensure_ascii=False))
print(len(cases),'annotated scenarios saved')
