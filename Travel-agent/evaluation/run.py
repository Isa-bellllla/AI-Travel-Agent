"""Run real model conversations; output traces for annotation, never fabricated rubric scores."""
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from travel_agent.agent import Agent
from travel_agent.data import Database
from travel_agent.llm import JsonLLM
from travel_agent.models import Session
from travel_agent.retrieval import HybridIndex
from evaluation.scoring import summarize

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cases',default='evaluation/cases.json')
    p.add_argument('--split',choices=['development','held_out','acceptance','regression'],default='development')
    p.add_argument('--output',default='evaluation/runs/latest.json')
    p.add_argument('--score-file',help='Summarize a human-annotated output without making LLM calls')
    args=p.parse_args()
    if args.score_file:
        print(json.dumps(summarize(json.loads(Path(args.score_file).read_text())),indent=2)); return
    load_dotenv()
    provider=JsonLLM(); db=Database(); agent=Agent(db,HybridIndex(db,provider),provider)
    cases=json.loads(Path(args.cases).read_text())
    if not any(case['split']==args.split for case in cases):
        p.error('No cases found for the selected split; no evaluation was run.')
    output=[]; failed=False
    for case in cases:
        if case['split']!=args.split: continue
        state=Session()
        for turn in case['turns']:
            try:
                result=agent.respond(turn,state)
                output.append(dict(result['trace'],case_id=case['id'],split=case['split'],
                    annotation=case['annotation'],stage='interim' if result['trace']['clarification'] else 'awaiting_review',
                    scores={'A':None,'B':None,'C':None},
                    model=getattr(provider,'model','unknown'),provider=getattr(provider,'provider','unknown')))
            except Exception as e:
                output.append({'case_id':case['id'],'user_message':turn,'error':str(e),
                               'scores':None,'stage':'failed','split':case['split'], 'dataset_sha256':db.digest,
                               'model':provider.model,'annotation':case['annotation'],'context':state.model_dump()})
                failed=True; break
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2))
    print(json.dumps(summarize(output),indent=2))
    if failed: raise SystemExit(1)

if __name__=='__main__': main()
