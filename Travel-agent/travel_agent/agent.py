import json
import time
from .models import Plan, Session, Query, Filter
from .prompts import INTERPRETER
from .grounding import Grounder
from .memory import update_search, clarification
from .responses import render_query
from .clarifications import resolve_answers, remember_question

DISCLAIMER='Prices are recorded USD/night references, not live quotes. Availability is not verified.'

class Agent:
    def __init__(self,db,index,provider):
        self.db=db; self.index=index; self.provider=provider; self.grounder=Grounder(db,provider)

    def respond(self,message,state:Session):
        if not message.strip(): raise ValueError('Please enter a message')
        if len(message)>12000: raise ValueError('Please shorten this message to 12,000 characters')
        started=time.perf_counter()
        # Work on a copy: malformed output/model failures cannot partially change memory.
        working=state.model_copy(deep=True); working.turn+=1
        trace={'turn':working.turn,'user_message':message,'context':state.model_dump(),
               'dataset_sha256':self.db.digest,'retrieval_mode':self.index.mode}
        t=time.perf_counter()
        plan=self.provider.structured(INTERPRETER,{
            'message':message,'state':working.model_dump(),
            'schema':{'columns':list(next(iter(self.db.records.values()))),
                      'locations':sorted({(r['city'],r['country']) for r in self.db.records.values()}),
                      'categories':sorted({r['category'] for r in self.db.records.values() if r['category']}),
                      'brands':sorted({r['brand'] for r in self.db.records.values() if r['brand']})},
            'hotel_candidates':self.db.planning_catalog(message, working.last_ids+working.focus_ids+working.pending_ids)},Plan)
        trace['interpretation_seconds']=time.perf_counter()-t
        trace['plan']=plan.model_dump(exclude_unset=True)
        working.status='paused' if plan.intent=='close' else 'active'
        update_search(working,plan,self.db)
        resolve_answers(working,plan,message)
        question,topic=clarification(plan,working)
        effective_intent='clarify' if question else ('recommend' if plan.intent=='clarify' else plan.intent)
        trace['extracted_preferences']=[p.model_dump() for p in working.preferences.values()]
        trace['slots']=dict(working.slots)
        if question:
            answer=question; working.pending_question=answer
            working.pending_topic=topic
            remember_question(working,plan,question,topic)
            cards=[]; result={}
        elif plan.intent=='close':
            answer='You’re welcome—glad I could help. You can come back with another question or change your preferences whenever you like.'
            working.pending_question=None
            working.pending_topic=None
            working.pending_ids=[]
            cards=[]; result=working.last_result
        elif plan.intent=='unsupported':
            answer='I can help with the hotels and reference prices in this database. It does not establish live availability, booking guarantees, current deals, or facts absent from hotel records. What would you like to explore within those records?'
            cards=[]; result={}
        else:
            t=time.perf_counter()
            execution_plan=plan.model_copy(update={'intent':effective_intent})
            answer,cards,result=self.execute(execution_plan,working,trace)
            trace['tools_and_grounding_seconds']=time.perf_counter()-t
            if trace.get('clarification_required') or result.get('needs_clarification'):
                effective_intent='clarify'
            else:
                working.pending_question=None
                working.pending_topic=None
                working.pending_ids=[]
        working.history.extend([{'role':'user','content':message},{'role':'assistant','content':answer}])
        working.last_result=result
        trace.update({'final_answer':answer,'final_ids':[c['id'] for c in cards],
                      'elapsed_seconds':time.perf_counter()-started,'intent':effective_intent,
                      'clarification':effective_intent=='clarify','result':result,
                      'clarification_memory':{k:v.model_dump() for k,v in working.clarification_memory.items()}})
        state.__dict__.update(working.__dict__)
        return {'answer':answer,'cards':cards,'trace':trace}

    def references(self,plan,state):
        if plan.use_focus:
            if not state.focus_ids: raise ValueError('There is no unambiguous hotel in focus. Please name the hotel.')
            return list(state.focus_ids)
        if plan.references:
            choices=state.pending_ids if state.pending_topic=='hotel_reference' and state.pending_ids else state.last_ids
            if any(i<1 or i>len(choices) for i in plan.references):
                raise ValueError('That hotel number is outside the latest list. Please choose one from it.')
            return [choices[i-1] for i in plan.references]
        return []

    def execute(self,plan,state,trace):
        if plan.intent=='query' and plan.additional_queries:
            # Run validated tools for each part without silently dropping compound questions.
            texts=[]; results=[]; tool_traces=[]
            for query in [plan.query]+plan.additional_queries:
                local_trace={}
                part=plan.model_copy(update={'query':query,'additional_queries':[]})
                text,_,result=self.execute(part,state,local_trace)
                texts.append(text); results.append(result); tool_traces.append(local_trace)
            trace['tool_runs']=tool_traces
            trace['selected_tools']=[t for item in tool_traces for t in item.get('selected_tools',[])]
            trace['query_parameters']=[item.get('query_parameters') for item in tool_traces]
            trace['retrieved_ids']=list(dict.fromkeys(i for item in tool_traces for i in item.get('retrieved_ids',[])))
            return '\n\n'.join(texts),[],{'answers':results}
        q=plan.query.model_copy(deep=True)
        ref=self.references(plan,state)
        if ref: q.ids=ref
        if q.ids and any(i not in self.db.records for i in q.ids): raise ValueError('Unknown hotel reference')
        recommendation=plan.intent=='recommend' or q.operation=='similar'
        prefs=list(state.preferences.values()) if recommendation else plan.add_preferences
        if recommendation:
            # Current structural slots replace obsolete tool constraints, rather than ANDing them.
            for field in ['city','country','category','brand']:
                if state.slots.get(field):
                    q.filters=[f for f in q.filters if f.field!=field]
                    q.filters.append(Filter(field=field,op='contains' if field=='brand' else 'eq',value=state.slots[field]))
        similar=q.ids[0] if q.operation=='similar' and len(q.ids)==1 else None
        if q.operation=='similar' and not similar: raise ValueError('Please select one hotel to find similar options.')
        if similar:
            q.ids=[]
            q.filters.extend([Filter(field=q.price_field,op='lt',value=self.db.records[similar][q.price_field]),
                              Filter(field='id',op='ne',value=similar)])
        trace['query_parameters']=q.model_dump()
        trace['selected_tools']=[q.operation if not recommendation else 'hybrid_recommendation']
        if not recommendation and not prefs:
            result=self.db.query(q)
            if q.operation=='detail' and not q.ids and result.get('count',0)>1:
                options='; '.join(str(n)+'. '+self.grounder.safe_text(r['name'])+' ('+self.grounder.safe_text(r['city'])+')' for n,r in enumerate(result.get('rows',[]),1))
                state.pending_question='Which hotel did you mean: '+options+'?'
                state.pending_topic='hotel_reference'
                state.pending_ids=[r['id'] for r in result.get('rows',[])]
                trace['clarification_required']=True
                return state.pending_question,[],{'needs_clarification':True,'matching_count':result['count']}
            trace['retrieved_ids']=[r['id'] for r in result.get('rows',[])]
            if q.operation in ['detail','compare'] and q.ids: state.focus_ids=list(q.ids)
            if q.operation=='list' and result.get('rows'):
                selected=[r['id'] for r in result['rows']]
                if ref or q.ids: state.focus_ids=selected
                else: state.last_ids=selected; state.focus_ids=[]
            return self.render_query(result,q,plan.requested_fields),[],result
        candidates=self.db.candidates(q)
        budget=state.slots.get('max_budget') if recommendation else None
        month=state.slots.get('month')
        if recommendation and budget and state.slots.get('budget_hard',True):
            candidates=[r for r in candidates if self.db.price(r,month)[0]<=budget and not r['estimated']]
        ranked=self.index.rank(plan.semantic_query,candidates,prefs,budget,month,similar)
        hard=[p for p in prefs if p.hard]
        # Semantic aggregates must verify every structured candidate, never count a top-k sample.
        aggregate=not recommendation and q.operation in ['count','min','max','mean','group']
        cap=80 if aggregate else 24
        inspected=ranked[:cap]
        evidence={}
        for start in range(0,len(inspected),8):
            evidence.update(self.grounder.verify(inspected[start:start+8],prefs))
        eligible=[r for r in inspected if all(self.grounder.satisfies(p,evidence.get(r['id'],[])) for p in hard)]
        total_weight=sum(p.priority for p in prefs)
        coverage={r['id']:{'matched_concepts':[p.concept for p in prefs if self.grounder.satisfies(p,evidence.get(r['id'],[]))],
                          'unverified_concepts':[p.concept for p in prefs if not self.grounder.satisfies(p,evidence.get(r['id'],[]))],
                          'weighted_coverage':sum(p.priority for p in prefs if self.grounder.satisfies(p,evidence.get(r['id'],[])))/total_weight if total_weight else None}
                  for r in inspected}
        trace['match_coverage']=coverage
        trace['coverage_note']='Evidence coverage of extracted semantic preferences, NOT rubric recognition of all user concepts.'
        trace.update({'candidate_count':len(candidates),'inspected_count':len(inspected),
                      'retrieved_ids':[r['id'] for r in inspected],
                      'evidence':{i:[e.model_dump() for e in es] for i,es in evidence.items()}})
        if aggregate:
            if len(inspected)<len(ranked):
                return ('This semantic calculation requires reviewing more records than the current verification limit. Please narrow the location or brand; I have not reported an incomplete count as a total.',[],{'incomplete':True})
            if not hard:
                return ('Please clarify which documented characteristic defines the group to calculate.',[],{'needs_clarification':True})
            if not eligible:
                return ('No records with verified supporting evidence were found. Missing descriptions can leave eligibility unknown, so this does not establish that the hotels lack the feature.',[],{'verified_count':0,'unknown_possible':True})
            result=self.db.query(q.model_copy(update={'ids':[r['id'] for r in eligible],'filters':[]}))
            result['scope_note']='Only records with verified explicit supporting evidence; missing evidence is unknown.'
            return self.render_query(result,q,[]),[],result
        if not eligible:
            complete=len(inspected)==len(ranked)
            if not ranked:
                msg='No records satisfy the structured location and price constraints. Which requirement would you like to relax?'
            else:
                msg='I found no verified match in '+('all structured candidates' if complete else 'the candidates reviewed')+'. Missing evidence is unknown; I will not assume a hard requirement is met. Which requirement would you like to relax or narrow?'
            return msg,[],{'verified_matches':0,'coverage_complete':complete}
        if recommendation and prefs:
            supported=[r for r in eligible if coverage[r['id']]['matched_concepts']]
            if not supported:
                question=('I couldn’t verify a match for those preferences in the hotel records reviewed. '
                          'Which preference matters most, or would you like to broaden the search?')
                state.pending_question=question
                state.pending_topic='unverified_preferences'
                return question,[],{'needs_clarification':True,'coverage_complete':len(inspected)==len(ranked)}
            eligible=supported
        # Evidence-weighted personalization after hard filtering; similarity alone cannot establish facts.
        eligible.sort(key=lambda r:-(coverage[r['id']]['weighted_coverage'] or 0))
        chosen=eligible[:(plan.requested_count or 3)] if recommendation else eligible[:q.limit]
        if not recommendation:
            result={'rows':chosen,'count':len(eligible),'price_field':q.price_field,
                    'scope_note':'Semantically verified candidates; may not cover the full database.'}
            text=self.render_query(result,q,plan.requested_fields)
            for r in chosen:
                for p in prefs:
                    snippets=[e for e in evidence.get(r['id'],[]) if e.preference==p.concept]
                    if snippets:
                        text+='\n\n'+self.grounder.safe_text(r['name'])+': '+ ' '.join('“'+self.grounder.safe_text(e.quote)+'” ('+e.field+')' for e in snippets)
                    else:
                        text+='\n\nFor '+self.grounder.safe_text(r['name'])+', the reviewed record does not establish '+self.grounder.safe_text(p.value)+'. Absence of evidence is not evidence of absence.'
            if q.operation=='detail' and q.ids: state.focus_ids=list(q.ids)
            return text,[],result
        old=list(state.last_ids)
        state.last_ids=[r['id'] for r in chosen]; state.focus_ids=[]
        shared={}
        for field in ('city','country','category','brand'):
            values={r[field] for r in chosen}
            if len(values)==1 and next(iter(values)):
                shared[field]=next(iter(values))
        from collections import Counter
        feature_counts=Counter(key for r in chosen for key in {
            self.grounder.feature_key(value) for value in self.grounder.feature_candidates(r)+[
                e.quote for e in evidence.get(r['id'],[]) if e.field in ('labels','description','benefits')]})
        cards=[{'id':r['id'],'text':self.grounder.card(r,evidence.get(r['id'],[]),prefs,month,budget,state.slots,
                                                    shared,feature_counts,position)} for position,r in enumerate(chosen)]
        place=', '.join(shared[k] for k in ('city','country') if shared.get(k))
        location=' in **'+self.grounder.safe_text(place)+'**' if place else ''
        noun='a stay' if len(chosen)==1 else str(len(chosen))+' stays'
        opening=('For your updated plans, I found ' if old else 'I found ')+noun+location+' for you.'
        if state.slots.get('category')==shared.get('category') and shared.get('category'):
            opening+=' I’ve focused on the **'+self.grounder.safe_text(shared['category'])+'** tier you asked for.'
        if state.slots.get('brand') and shared.get('brand'):
            opening+=' These follow your **'+self.grounder.safe_text(state.slots['brand'])+'** brand preference.'
        opening+=(' Here’s what makes it worth a closer look.' if len(chosen)==1 else ' Here’s what gives each option its appeal.')
        if similar: opening+=' These have a lower recorded '+q.price_field.replace('_',' ')+' than the selected hotel.'
        if len(chosen)<(plan.requested_count or 3):
            opening+=' These are the closest checked matches I found, so I’d focus on them rather than stretch the list.'
        answer=opening+'\n\n'+'\n\n'.join(c['text'] for c in cards)+'\n\n'+DISCLAIMER
        if len(inspected)<len(ranked): answer+=' There may be other suitable stays beyond the options reviewed.'
        return answer,cards,{'recommended_ids':list(state.last_ids),'coverage_complete':len(inspected)==len(ranked)}

    def render_query(self,result,q,fields):
        return render_query(result,q,fields,DISCLAIMER)
