"""Deterministic tools only; never reports a conversational quality score."""
import json, statistics, time
from pathlib import Path
from travel_agent.data import Database
from travel_agent.models import Query, Filter

def main():
 db=Database(); durations=[]; checks=0
 for city in sorted({r['city'] for r in db.records.values()}):
  actual=[r for r in db.records.values() if r['city']==city]
  for op in ['count','min','max','mean']:
   q=Query(filters=[Filter(field='city',op='eq',value=city)],operation=op,price_field='peak_price')
   started=time.perf_counter(); result=db.query(q); durations.append(time.perf_counter()-started)
   if op=='count': assert result['count']==len(actual)
   else:
    v=[r['peak_price'] for r in actual]
    expected=sum(v)/len(v) if op=='mean' else min(v) if op=='min' else max(v)
    assert abs(result[op]-expected)<1e-7
   checks+=1
 output={'scope':'Deterministic database tools, NOT LLM evaluation','dataset_sha256':db.digest,
         'queries_checked':checks,'cities':141,'all_correct':True,
         'mean_seconds':statistics.mean(durations),'median_seconds':statistics.median(durations),
         'p95_seconds_nearest_rank':sorted(durations)[int(.95*len(durations)+.999999)-1],
         'llm_cases_scored':0,'rubric_score':None}
 Path('docs/tool_benchmark.json').write_text(json.dumps(output,indent=2))
 print(json.dumps(output,indent=2))

if __name__=='__main__': main()
