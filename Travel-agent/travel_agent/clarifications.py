"""Track what was asked, what the user answered, and which uncertainty is resolved."""
from .models import ClarificationRecord

# Canonical state/topic bindings, not user-message keyword matching.
TOPIC_SLOT={'category':'category','accommodation_level':'category','brand_level':'category',
            'brand':'brand','city':'city','country':'country','budget':'max_budget'}


def slot_known(state, slot):
    if slot=='max_budget':
        return state.slots.get('max_budget') is not None or state.slots.get('budget_kind') in ('skipped','flexible')
    return state.slots.get(slot) not in (None,'')


def resolve_answers(state,plan,message):
    if plan.intent not in ('recommend','clarify'):
        return
    patch=plan.slots.model_dump(exclude_unset=True)
    for key in plan.confirmed_preferences:
        if key in state.preferences:
            state.preferences[key]=state.preferences[key].model_copy(update={'confirmed':True,'confidence':1.0})
    for topic,record in state.clarification_memory.items():
        slot=record.target_slot or TOPIC_SLOT.get(topic)
        slot_answered=bool(slot and slot in patch and slot_known(state,slot))
        if slot=='max_budget' and patch.get('budget_kind') in ('skipped','flexible'):
            slot_answered=True
        updated_keys={p.concept for p in plan.add_preferences if p.confirmed}
        keys_answered=bool(record.preference_keys) and all(
            key in plan.remove_preferences or key in plan.confirmed_preferences or key in updated_keys
            or any(key in p.replaces and p.confirmed for p in plan.add_preferences)
            for key in record.preference_keys)
        explicit=topic in plan.resolved_topics and (
            bool(slot and slot_known(state,slot)) or keys_answered)
        if slot_answered or keys_answered or explicit:
            record.status='skipped' if slot=='max_budget' and state.slots.get('budget_kind')=='skipped' else 'answered'
            record.answer=message
            record.resolved_turn=state.turn
            record.values={slot:state.slots.get(slot)} if slot else {}
            if slot=='max_budget': record.values['budget_kind']=state.slots.get('budget_kind')
            record.values.update({f'preference:{k}':state.preferences[k].model_dump() for k in record.preference_keys if k in state.preferences})
    return


def need_resolved(need,state):
    if need.reason=='conflict':
        return False
    record=state.clarification_memory.get(need.topic)
    target=need.target_slot or TOPIC_SLOT.get(need.topic)
    if record is None and target:
        record=next((r for r in state.clarification_memory.values() if r.target_slot==target and r.status!='pending'),None)
    if not record or record.status=='pending':
        # A typed field supplied by this or an earlier turn is not missing.
        return need.reason=='missing' and bool(need.target_slot and slot_known(state,need.target_slot))
    if need.target_slot and record.target_slot and need.target_slot!=record.target_slot:
        return False
    if need.preference_keys and set(need.preference_keys)!=set(record.preference_keys):
        return False
    # Changes invalidate old resolutions; an unchanged confirmed answer cannot be asked for again.
    for key,value in record.values.items():
        if key.startswith('preference:'):
            pref=state.preferences.get(key.split(':',1)[1])
            if pref is None or pref.model_dump()!=value: return False
        elif state.slots.get(key)!=value:
            return False
    return bool(record.values)


def remember_question(state,plan,question,topic):
    if not topic:
        return
    need=next((n for n in plan.clarification_needs if n.topic==topic),None)
    slot=need.target_slot if need and need.target_slot else TOPIC_SLOT.get(topic)
    keys=need.preference_keys if need else []
    if not keys and topic=='experience':
        keys=[p.concept for p in state.preferences.values() if not p.confirmed or p.confidence<0.7][:1]
    if not keys and slot=='category':
        keys=[p.concept for p in state.preferences.values() if p.target_field=='category' or p.dimension=='accommodation_level']
    state.clarification_memory[topic]=ClarificationRecord(question=question,source_turn=state.turn,
                                                        target_slot=slot,preference_keys=keys)
