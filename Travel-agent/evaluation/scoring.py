"""Official rubric: explicit human judgments, no proxy passes for subjective criteria."""
import math
import statistics

def summarize(records):
    complete=[]; interim=[]; clarification_latencies=[]; latencies=[]
    for r in records:
        if r.get('error'):
            continue
        if r.get('clarification'):
            clarification_latencies.append(r['elapsed_seconds'])
        if r.get('elapsed_seconds') is not None: latencies.append(r['elapsed_seconds'])
        scores=r.get('scores') or {}
        if r.get('stage')=='interim':
            if scores.get('B') is not None: raise ValueError('Interim clarification B must be N/A')
            interim.append(r); continue
        if r.get('stage')=='completed' and all(type(scores.get(k)) is int and scores[k] in (0,1) for k in 'ABC'):
            complete.append(r)
    n=len(complete)
    totals=[sum(r['scores'][k] for k in 'ABC') for r in complete]
    ordered=sorted(latencies)
    return {'completed_scored_cases':n,'interim_cases':len(interim),
        'unscored_or_failed_records':len(records)-n-len(interim),
        'average_out_of_3':sum(totals)/n if n else None,
        'normalized_percent':sum(totals)/(3*n)*100 if n else None,
        'criterion_pass_percent':{k:sum(r['scores'][k] for r in complete)/n*100 if n else None for k in 'ABC'},
        'perfect_case_percent':sum(t==3 for t in totals)/n*100 if n else None,
        'latency':{'mean':statistics.mean(latencies) if latencies else None,
                   'median':statistics.median(latencies) if latencies else None,
                   'p95_nearest_rank':ordered[math.ceil(.95*len(ordered))-1] if ordered else None,
                   'clarification_within_45_seconds':sum(t<=45 for t in clarification_latencies)/len(clarification_latencies) if clarification_latencies else None},
        'note':'Only completed, explicitly scored A/B/C cases enter quality denominators. No automatic subjective scores.'}
