"""Conversational presentation of deterministic results; no raw JSON answers."""
from .grounding import Grounder

LABELS = {
    'name':'Hotel', 'city':'City', 'country':'Country', 'brand':'Brand', 'category':'Recorded tier',
    'labels':'Highlights', 'description':'About the stay', 'benefits':'Recorded benefits',
    'peak_months':'Peak-season months', 'off_months':'Off-season months',
    'peak_sample':'Peak-season sampling month', 'off_sample':'Off-season sampling months',
    'remark':'Source note', 'estimated':'Price marked as estimated',
    'off_price':'Off-season reference rate', 'peak_price':'Peak-season reference rate',
}


def render_query(result, q, fields, disclaimer):
    s = Grounder.safe_text
    season = 'peak-season' if q.price_field == 'peak_price' else 'off-season'
    def money(value): return f'USD {value:,.2f}'
    def prices(r):
        label = 'Estimated reference' if r['estimated'] else 'Reference'
        return f"{label} rates: **{money(r['off_price'])} off-season / {money(r['peak_price'])} peak-season per night**."
    def value(r, field):
        if field in ('peak_months','off_months') and not r[field]:
            return (f"{LABELS[field]} are not recorded for this hotel, so I can’t confirm them "
                    'from this dataset. A listed seasonal price alone does not establish the months.')
        if field in ('off_price','peak_price'):
            return f"{LABELS[field]}: {money(r[field])}/night" + (' (estimated).' if r['estimated'] else '.')
        if field == 'estimated':
            return LABELS[field]+': '+('yes.' if r[field] else 'no.')
        return f"**{LABELS.get(field, field.replace('_',' ').capitalize())}:** "+(s(r[field]) if r[field] else 'Not recorded; unknown.')

    if 'rows' in result:
        if not result['rows']:
            return 'I couldn’t find a matching hotel record. Could you confirm the hotel name or broaden the search?'
        parts = []
        for n,r in enumerate(result['rows'],1):
            lines = [f"**{n}. {s(r['name'])}** — {s(r['city'])}, {s(r['country'])}"]
            if q.operation != 'detail' or not fields:
                lines.append(prices(r))
            desired = fields or (['category','labels','description','benefits','peak_months','off_months'] if q.operation=='detail' else [])
            lines.extend(value(r,f) for f in desired if f in r and f not in ('id','name'))
            parts.append('\n\n'.join(lines))
        text = '\n\n'.join(parts)
    elif q.operation == 'count':
        text = f"I found **{result['count']} hotel records** matching your question."
    elif q.operation in ('min','max','mean'):
        answer = result[q.operation]
        if answer is None:
            text = 'There are no matching prices to calculate from.'
        else:
            title = {'mean':'average','min':'lowest','max':'highest'}[q.operation]
            text = (f"The **{title} recorded {season} price is {money(answer)} per night**, "
                    f"based on {result['count']} matching hotel records.")
    elif 'groups' in result:
        metric = 'Hotel count' if q.metric=='count' else {'mean':'Average','min':'Lowest','max':'Highest'}[q.metric]+f' {season} rate (USD/night)'
        lines = [f"Here is the breakdown by {q.group_by}:",
                 f"| {LABELS.get(q.group_by,q.group_by)} | {metric} |", '|---|---:|']
        for group in result['groups']:
            v=group[q.metric]
            shown=str(v) if q.metric=='count' else f'{v:,.2f}' if v is not None else 'Unknown'
            lines.append(f"| {s(group[q.group_by])} | {shown} |")
        text='\n\n'.join(lines[:1])+'\n\n'+'\n'.join(lines[1:])
    elif 'seasonal' in result:
        parts=[]
        for r in result['seasonal']:
            d=r['difference_usd']
            comparison=f"{money(abs(d))} {'higher' if d>=0 else 'lower'}"
            percent=f" ({abs(r['change_percent']):.1f}%)" if r['change_percent'] is not None else ''
            parts.append(f"**{s(r['name'])}**\n\n"+prices(r)+
                         f"\n\nThe peak-season reference is {comparison} than the off-season reference{percent}."+
                         (' These values are estimates.' if r['estimated'] else ''))
        text='\n\n'.join(parts) or 'There are no matching seasonal prices to compare.'
    else:
        raise ValueError('Unsupported database result')
    includes_estimates = result.get('includes_estimates') or any(g.get('includes_estimates') for g in result.get('groups',[]))
    if includes_estimates:
        text+='\n\nThis calculation includes estimated reference prices.'
    if result.get('scope_note'):
        text+='\n\n'+result['scope_note']
    if any(f.field=='brand' for f in q.filters):
        text+='\n\nI used the recorded brand text, without inferring corporate ownership.'
    return text+'\n\n'+disclaimer
