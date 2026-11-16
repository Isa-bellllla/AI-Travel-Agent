from .models import EvidenceBatch, Evidence
from .prompts import VERIFIER

class Grounder:
    def __init__(self,db,provider): self.db=db; self.provider=provider
    def verify(self,rows,preferences):
        if not preferences: return {r['id']:[] for r in rows}
        verified={r['id']:[] for r in rows}
        semantic=[]
        for p in preferences:
            field=p.target_field or ('category' if p.dimension=='accommodation_level' else None)
            if field not in ('category','brand','city','country'):
                semantic.append(p)
                continue
            if p.evidence_scope!='hotel':
                continue
            desired=p.normalized_value or p.value
            if field=='category' and desired not in ('high-end','Top Luxury','International chain'):
                continue  # Unmapped tier is unresolved, never proved by free text.
            for row in rows:
                source=row[field]
                if not source:
                    continue
                matches=desired.casefold() in source.casefold() if field=='brand' else desired.casefold()==source.casefold()
                verified[row['id']].append(Evidence(preference=p.concept,field=field,quote=source,
                    supports=matches,relation='hotel_property'))
        if not semantic:
            return verified
        result=self.provider.structured(VERIFIER,{'preferences':[p.model_dump() for p in semantic],
                    'records':rows},EvidenceBatch)
        allowed={r['id']:r for r in rows}; concepts={p.concept:p for p in semantic}
        for item in result.hotels:
            if item.id not in allowed: continue
            for e in item.evidence:
                pref=concepts.get(e.preference)
                if pref is None: continue
                fields={pref.target_field} if pref.target_field else {'labels','description','benefits'}
                expected='hotel_location_relation' if pref.evidence_scope=='proximity' else 'hotel_property'
                # Exact quotes, correct field AND correct subject/relation are separate checks.
                # Relation/entailment is still an LLM judgment and requires real-model review.
                if e.field in fields and e.relation==expected and e.quote in allowed[item.id][e.field]:
                    verified[item.id].append(e)
        return verified

    @staticmethod
    def satisfies(preference,evidence):
        matching=[e for e in evidence if e.preference==preference.concept]
        expected=not preference.negated
        return any(e.supports==expected for e in matching) and not any(e.supports!=expected for e in matching)

    @staticmethod
    def safe_text(text):
        # Plain text -> Markdown escapes -> HTML text escapes. Do not escape quote
        # characters or Markdown-escape the '#' inside a newly created HTML entity.
        import html
        text=html.unescape(str(text))
        for char in ['\\','`','*','_','[',']','#','!','|','$']:
            text=text.replace(char,'\\'+char)
        return html.escape(text,quote=False)

    @staticmethod
    def feature_key(text):
        import re
        return ''.join(re.findall(r'\w+',str(text).casefold()))

    @classmethod
    def feature_candidates(cls,row):
        # Keep source wording; structural matches are filters, not selling points.
        structural={cls.feature_key(row.get(k,'')) for k in ('city','country','category','brand','name')}
        parts=[v.strip() for v in row['labels'].split('/') if v.strip()]
        parts=[v for v in parts if cls.feature_key(v) not in structural]
        if not parts and row.get('description'):
            parts=[row['description']]
        return list(dict.fromkeys(parts))

    def card(self,row,evidence,preferences,month=None,budget=None,search=None,shared=None,feature_counts=None,position=0):
        s=self.safe_text
        price,season=self.db.price(row,month)
        shared=shared or {}
        feature_counts=feature_counts or {}
        structural={'city','country','category','brand','name'}
        values={self.feature_key(row.get(k,'')) for k in structural}
        relevant=[(p,e) for p in preferences for e in evidence
                  if e.preference==p.concept and e.supports==(not p.negated)
                  and e.field not in structural and p.target_field not in structural
                  and p.dimension!='accommodation_level'
                  and self.feature_key(e.quote) not in values]
        lines=[f"### {s(row['name'])}"]
        if not (shared.get('city') and shared.get('country')):
            place=s(row['city']) if shared.get('country') else s(row['city'])+', '+s(row['country'])
            lines.append('In **'+place+'**.')
        # Prefer evidence matching user needs, then less-repeated actual source highlights.
        selected=[]
        for pref,quote in sorted(relevant,key=lambda pair:(-pair[0].priority,feature_counts.get(self.feature_key(pair[1].quote),1))):
            key=self.feature_key(quote.quote)
            if any(key in self.feature_key(v) or self.feature_key(v) in key for v in selected): continue
            selected.append(quote.quote)
            if len(selected)>=2: break
        candidates=self.feature_candidates(row)
        ordered=sorted(enumerate(candidates),key=lambda item:(feature_counts.get(self.feature_key(item[1]),1),item[0]))
        for _,feature in ordered:
            if len(selected)>=2: break
            key=self.feature_key(feature)
            if any(key in self.feature_key(v) or self.feature_key(v) in key for v in selected): continue
            selected.append(feature)
        selected.sort(key=lambda value:feature_counts.get(self.feature_key(value),1))
        if selected:
            lead=('The appeal here is ', 'For this stay, I’d draw your attention to ', 'A couple of details worth a closer look: ')[position % 3]
            lines.append(lead+' and '.join('**'+s(v)+'**' for v in selected)+'.')
        else:
            lines.append('The record is light on descriptive details, so I’d confirm the features that matter to you before deciding.')
        label='estimated reference rates' if row['estimated'] else 'reference rates'
        lines.append(f"For planning, you’re looking at {label} of "
                     f"**USD {row['off_price']:,.2f} per night off-season** and "
                     f"**USD {row['peak_price']:,.2f} in peak season**.")
        if budget:
            basis='the higher recorded rate' if season=='unknown' else 'the recorded '+season+'-season rate'
            if price<=budget:
                lines.append(f"That fits your USD {budget:,.2f} reference budget using {basis}.")
            else:
                lines.append(f"One thing to weigh up: using {basis}, it exceeds your USD {budget:,.2f} reference budget.")
        if season!='unknown':
            lines.append(f"For your month, the {season}-season reference is USD {price:,.2f}/night.")
        unsupported=[p.value for p in preferences if not self.satisfies(p,evidence)]
        if unsupported:
            lines.append('Before you decide, I’d want to confirm '+', '.join(s(v) for v in unsupported)+
                         '; those details aren’t established in this hotel’s record.')
        if row['estimated']:
            lines.append('A quick note on price: these figures are marked as estimates, rather than confirmed rates.')
        if row['peak_months']:
            lines.append('For timing, keep **'+s(row['peak_months'])+'** in mind: those are the listed peak-season months.')
        elif month or budget:
            lines.append('The seasonal months for this stay aren’t recorded, so I wouldn’t assume which season your dates fall into.')
        return '\n\n'.join(lines)
