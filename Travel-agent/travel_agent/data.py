"""Immutable source records and allowlisted, read-only SQLite queries."""
import csv
import hashlib
import sqlite3
import calendar
import math
import re
from collections import Counter
from pathlib import Path
from .models import Query

DATA = Path(__file__).resolve().parents[1] / 'cleaned_hotels.csv'
COLUMNS = {'Country':'country','City':'city','Hotel Name':'name','brand':'brand',
 'Brand level':'category','Off-season price (USD/night)':'off_price',
 'Peak season price (USD/night)':'peak_price','Peak season months':'peak_months',
 'Off-season months':'off_months','Peak season sampling month':'peak_sample',
 'Off-season sampling months':'off_sample','Label':'labels','courtesy':'benefits',
 'Reasons for recommendation':'description','Remark':'remark','price_missing':'estimated'}
FIELDS = set(COLUMNS.values()) | {'id'}
OPS = {'eq':'=', 'ne':'!=','lt':'<','lte':'<=','gt':'>','gte':'>='}

class Database:
    def __init__(self, path=DATA):
        self.path = Path(path)
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.records = {}
        with self.path.open(encoding='utf-8-sig',newline='') as f:
            reader = csv.DictReader(f)
            if set(reader.fieldnames or []) != set(COLUMNS):
                raise ValueError('Dataset schema changed; audit required')
            for source in reader:
                row = {new:source[old] for old,new in COLUMNS.items()}
                key = '\0'.join(row[k] for k in ['country','city','name'])
                row['id'] = 'h_' + hashlib.sha256(key.encode()).hexdigest()[:16]
                for k in ['off_price','peak_price']: row[k] = float(row[k])
                if source['price_missing'] not in ('True','False'): raise ValueError('Invalid price_missing')
                row['estimated'] = source['price_missing'] == 'True'
                if row['id'] in self.records: raise ValueError('Duplicate hotel identity')
                self.records[row['id']] = row
        self.conn = sqlite3.connect(':memory:', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        fields = ['id'] + list(COLUMNS.values())
        declaration = ','.join(f'{f} ' + ('REAL' if f in ['off_price','peak_price'] else 'INTEGER' if f=='estimated' else 'TEXT') for f in fields)
        self.conn.execute(f'CREATE TABLE hotels ({declaration})')
        self.conn.executemany(f'INSERT INTO hotels VALUES ({",".join("?" for _ in fields)})',
                              [[r[f] for f in fields] for r in self.records.values()])
        self.conn.commit()
        self.conn.execute('PRAGMA query_only=ON')

    def planning_catalog(self, message, remembered_ids=()):
        """Entity candidates for interpretation, not factual answers or intent rules."""
        tokens = set(re.findall(r"\w+", message.casefold()))
        names = {i: set(re.findall(r"\w+", r['name'].casefold())) for i,r in self.records.items()}
        frequency = Counter(t for terms in names.values() for t in terms)
        scores = {i:sum(math.log(1+len(names)/frequency[t]) for t in tokens & terms)
                  for i,terms in names.items()}
        selected = list(dict.fromkeys(list(remembered_ids)+[
            i for i in sorted(scores,key=lambda i:-scores[i]) if scores[i]>0][:12]))
        return [{k:self.records[i][k] for k in ('id','name','city','country','category')}
                for i in selected if i in self.records]

    def query(self, q: Query):
        clauses, values = [], []
        for f in q.filters:
            if f.op == 'contains':
                if f.field in ['off_price','peak_price','estimated']: raise ValueError('contains requires text')
                clauses.append(f'instr(lower({f.field}), lower(?)) > 0')
            else:
                clauses.append(f'{f.field} {OPS[f.op]} ? COLLATE NOCASE')
            values.append(f.value)
        if q.ids:
            if any(i not in self.records for i in q.ids): raise ValueError('Unknown hotel ID')
            clauses.append(f'id IN ({",".join("?" for _ in q.ids)})'); values.extend(q.ids)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        rows = [dict(r) for r in self.conn.execute('SELECT * FROM hotels'+where, values)]
        # Calculations are deterministic; never execute model-generated SQL/Python.
        count = len(rows)
        field = q.price_field
        if q.operation == 'count': result = {'count':count}
        elif q.operation in ['min','max','mean']:
            result = {q.operation: self._aggregate(rows,field,q.operation),'count':count,'price_field':field,
                      'includes_estimates':any(r['estimated'] for r in rows)}
        elif q.operation == 'seasonal':
            rows.sort(key=lambda r:(r[field],r['id']),reverse=q.sort_desc)
            result = {'seasonal': [{'id':r['id'],'name':r['name'],'off_price':r['off_price'],
                'peak_price':r['peak_price'],'difference_usd':r['peak_price']-r['off_price'],
                'change_percent':(r['peak_price']/r['off_price']-1)*100 if r['off_price'] else None,
                'estimated':bool(r['estimated']),'peak_months':r['peak_months'],'off_months':r['off_months']}
                for r in rows[:q.limit]], 'count':count, 'price_field':field,
                'includes_estimates':any(r['estimated'] for r in rows)}
        elif q.operation == 'group':
            if not q.group_by: raise ValueError('group_by required')
            groups = {}
            for r in rows: groups.setdefault(r[q.group_by] or '(not recorded)',[]).append(r)
            result = {'groups':[{q.group_by:k, q.metric:len(v) if q.metric=='count' else self._aggregate(v,field,q.metric),
                                  'includes_estimates':any(r['estimated'] for r in v)} for k,v in sorted(groups.items())],
                      'count':count,'price_field':field}
        else:
            if q.operation in ['compare','detail'] and q.ids:
                rows.sort(key=lambda r:q.ids.index(r['id']))
            else: rows.sort(key=lambda r:(r[field],r['id']),reverse=q.sort_desc)
            result = {'rows':rows[:q.limit], 'count':count, 'price_field':field}
        return result

    @staticmethod
    def _aggregate(rows,field,op):
        if not rows: return None
        values=[r[field] for r in rows]
        return sum(values)/len(values) if op=='mean' else min(values) if op=='min' else max(values)

    def candidates(self, q):
        # All structured matches, without the display limit.
        return self._all(q)

    def _all(self,q):
        # Safe pagination independent of the display limit, through the same validated filters.
        ids = []
        for start in range(0,len(self.records),20):
            batch=list(self.records)[start:start+20]
            selected=[i for i in batch if not q.ids or i in q.ids]
            if not selected: continue
            result=self.query(q.model_copy(update={'operation':'list','ids':selected,'limit':20}))
            ids.extend(r['id'] for r in result['rows'])
        return [self.records[i] for i in ids]

    def price(self, row, month=None):
        if month:
            name=calendar.month_name[month].casefold()
            peak=name in row['peak_months'].casefold()
            off=name in row['off_months'].casefold()
            if peak != off: return (row['peak_price'] if peak else row['off_price']), ('peak' if peak else 'off')
        return max(row['off_price'],row['peak_price']), 'unknown'

    @staticmethod
    def document(row):
        return '\n'.join(f'{k}: {row[k]}' for k in ['name','city','country','brand','category','labels','description','benefits'])
