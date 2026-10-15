"""Kiểm tra truy vết đầu ra, tạo mẫu âm để rà soát ứng viên bị bỏ sót."""
import json
import random
import re
from collections import Counter,defaultdict
from extract_pillar_evidence import ROOT,read_csv,write_csv,ENTITY_RX


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    out=ROOT/'output/processed/evidence'
    docs={r['doc_id']:r for r in read_csv(out/'source_documents.csv')}
    rows=list(read_csv(out/'evidence_candidates.csv'))
    assert len({r['evidence_id'] for r in rows})==len(rows)
    for r in rows:
        d=docs[r['doc_id']]
        assert r['quote'] in d['text']
        assert r['source_id']==d['source_id'] and r['input_path']==d['input_path']
        assert r['entity'] in ('ZaloPay','VPBank','VCB','HDBank','ACB','VNG')
        if r['source']=='app_review':assert r['pillar'] in ('P3','P5')
        if r['tagged_entity']=='VNG' and r['entity']=='ZaloPay':assert ENTITY_RX['ZaloPay'].search(r['quote'])
        if r['source'].endswith('report'):assert int(r['pdf_page'])>=1
    summary=list(read_csv(out/'pillar_coverage.csv'))
    assert sum(int(r['candidate_rows']) for r in summary)==len(rows)
    known={(r['doc_id'],r['quote']) for r in rows}
    negatives=defaultdict(list)
    for doc_id,d in docs.items():
        for match in re.finditer(r'.+?(?:[.!?;](?=\s+[^\W\d_])|$)',d['text']):
            quote=match.group().strip()
            if 40<=len(quote)<=1000 and (doc_id,quote) not in known:
                negatives[d['source']].append(dict(doc_id=doc_id,entity=d['entity'],source=d['source'],quote=quote,url=d['url'],pdf_page=d['page'],human_missed_evidence='',human_pillar='',human_note=''))
    rng=random.Random(20261015)
    sample=[]
    for group in negatives.values():sample.extend(rng.sample(group,min(10,len(group))))
    write_csv(out/'negative_control_sample.csv',sample,list(sample[0]))
    stats=dict(documents=len(docs),verified_candidates=len(rows),all_quotes_traceable=True,review_limitations_verified=True,candidates_by_source=dict(Counter(r['source'] for r in rows)),claim_statuses=dict(Counter(r['claim_status'] for r in rows)),negative_control_sample=len(sample),note='Kiểm tra kỹ thuật, chưa phải precision/recall hoặc nhãn chuẩn')
    (out/'verification.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
