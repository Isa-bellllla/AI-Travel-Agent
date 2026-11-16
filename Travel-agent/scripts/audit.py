"""Reproduce the dataset audit and extract the original evaluation specification."""
import csv, collections, hashlib, json, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    with (ROOT/'cleaned_hotels.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); rows=list(reader)
        report={'rows':len(rows),'columns':{},'sha256':hashlib.sha256((ROOT/'cleaned_hotels.csv').read_bytes()).hexdigest()}
        for column in reader.fieldnames:
            values=[r[column] for r in rows]
            report['columns'][column]={'missing':sum(not v.strip() for v in values),'unique':len(set(values))}
        report['categorical_values']={k:dict(collections.Counter(r[k] for r in rows)) for k in ['Brand level','brand','price_missing']}
        report['price_ranges']={k:[min(float(r[k]) for r in rows),max(float(r[k]) for r in rows)] for k in ['Off-season price (USD/night)','Peak season price (USD/night)']}
        report['unique_location_keys']=len({(r['Country'],r['City'],r['Hotel Name']) for r in rows})
        report['countries']=len({r['Country'] for r in rows}); report['cities']=len({r['City'] for r in rows})
    (ROOT/'docs/data_audit.json').write_text(json.dumps(report,indent=2))
    with zipfile.ZipFile(ROOT/'Travel_AI_Agent_Evaluation_Rubric_v1.docx') as z:
        assert z.testzip() is None
        root=ET.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        lines=[''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in root.findall('.//w:p',ns)]
    (ROOT/'docs/rubric_extracted.txt').write_text('\n'.join(line for line in lines if line))
    print('Audit and original rubric extraction saved to docs/')

if __name__=='__main__': main()
