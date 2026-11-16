"""Reconcile semantic model updates with deterministic state invariants."""
from .clarifications import need_resolved, TOPIC_SLOT, slot_known
from .models import ClarificationNeed


def update_search(state, plan, db):
    # Information questions must not silently rewrite the user's travel preferences.
    if plan.intent not in ('recommend', 'clarify'):
        return
    if plan.search_action == 'new_search':
        state.preferences.clear()
        state.slots.clear()
        state.last_ids.clear()
        state.focus_ids.clear()
        state.pending_question = None
        state.pending_topic = None
        state.pending_ids.clear()
        state.clarification_memory.clear()
    for key in plan.remove_preferences:
        state.preferences.pop(key, None)
    for pref in plan.add_preferences:
        for key in pref.replaces:
            state.preferences.pop(key, None)
        if pref.dimension:
            # A dimension is exclusive only if explicitly declared by the interpreter.
            for key, previous in list(state.preferences.items()):
                if previous.dimension == pref.dimension and key != pref.concept:
                    state.preferences.pop(key)
        state.preferences[pref.concept] = pref.model_copy(update={'source_turn': state.turn})
    patch = plan.slots.model_dump(exclude_unset=True)
    for key, value in patch.items():
        if value is None:
            state.slots.pop(key, None)
        else:
            state.slots[key] = value

    # Derive location relations from actual records, never from model world knowledge.
    if patch.get('city'):
        matches = [r for r in db.records.values() if r['city'].casefold() == patch['city'].casefold()]
        countries = {r['country'] for r in matches}
        if matches:
            state.slots['city'] = matches[0]['city']
        if len(countries) == 1:
            state.slots['country'] = countries.pop()
        elif 'country' not in patch:
            state.slots.pop('country', None)
    elif patch.get('country'):
        city = state.slots.get('city')
        compatible = any(r['city'].casefold() == (city or '').casefold()
                         and r['country'].casefold() == patch['country'].casefold()
                         for r in db.records.values())
        if city and not compatible:
            state.slots.pop('city', None)
    if patch.get('category'):
        # Category is one replaceable structural slot, never two additive tiers.
        for key, p in list(state.preferences.items()):
            if p.dimension == 'accommodation_level' or p.target_field=='category':
                state.preferences.pop(key)
    if patch.get('budget_kind') == 'subjective':
        state.slots.pop('max_budget', None)
        state.slots.pop('budget_hard', None)
    elif patch.get('budget_kind') == 'flexible':
        state.slots['budget_hard'] = False
    elif patch.get('budget_kind') == 'skipped':
        state.slots.pop('max_budget', None)
        state.slots.pop('budget_hard', None)
    elif patch.get('max_budget') is not None:
        state.slots['budget_hard'] = patch.get('budget_hard', True)
        state.slots['budget_kind'] = patch.get('budget_kind') or 'numeric'


def clarification(plan, state):
    """Policy over interpreted uncertainty, not keyword matching of user messages."""
    if plan.intent in ('query', 'unsupported', 'close'):
        return None, None
    needs = sorted((n for n in plan.clarification_needs if n.material and not need_resolved(n,state)), key=lambda n: -n.priority)
    if needs:
        return needs[0].question, needs[0].topic
    if plan.unresolved_concepts:
        terms='; '.join(plan.unresolved_concepts[:3])
        return ('Could you explain what you mean by '+terms+' for this stay? '
                'I’d like to understand that before narrowing the hotels.'), 'meaning'
    unbound=[p for p in state.preferences.values() if (p.target_field=='category' or p.dimension=='accommodation_level')
             and (p.normalized_value or p.value) not in ('high-end','Top Luxury','International chain')]
    if unbound:
        return ('Which recorded hotel tier do you mean: high-end, Top Luxury, or International chain?'), 'category'
    uncertain=[p for p in state.preferences.values() if not p.confirmed or p.confidence<0.7]
    if uncertain:
        return ('When you say '+uncertain[0].value+', what would that look like in your ideal hotel stay?'), 'experience'
    location_in_query=any(f.field in ('city','country','name','id') for f in plan.query.filters) or bool(plan.query.ids)
    if not any(state.slots.get(k) for k in ('city','country','exploratory')) and not location_in_query and not plan.references and not plan.use_focus:
        if plan.intent=='clarify' and plan.question and plan.question_topic in (None,'destination'):
            return plan.question, plan.question_topic
        return ('Do you have a country or city in mind, or would you like me to suggest destinations too?'), 'destination'
    if state.slots.get('budget_kind') == 'subjective':
        return ('What nightly budget in USD would feel comfortable for you? A rough range is fine, '
                'or I can compare the lower-priced options without a fixed limit.'), 'budget'
    if plan.intent == 'clarify':
        topic=plan.question_topic
        slot=TOPIC_SLOT.get(topic)
        record=state.clarification_memory.get(topic)
        answered=bool(record and need_resolved(ClarificationNeed(topic=topic,question=plan.question or 'Clarification',target_slot=slot),state))
        if not answered and not (slot and slot_known(state,slot)):
            return plan.question, topic
    return None, None
