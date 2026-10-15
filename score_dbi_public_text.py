"""DBI từ sắc thái công khai; trọng số cố định, không thưởng số lượng bài."""
import csv
import hashlib
import json
import re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

from sentiment_module import sentence_evidence,DIGITAL_CONTEXT
from extract_pillar_evidence import norm,stage,ENTITY_RX

ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'dbi_public_text_config.json').read_text(encoding='utf-8'))
COMPANIES=('VNG (VNZ)','VPBank','VCB','HDBank','ACB')
PATTERNS={p:{i:re.compile(r'(?<!\w)(?:'+rx+r')(?!\w)',re.I) for i,rx in v['indicators'].items()} for p,v in CONFIG['pillars'].items()}


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as h:yield from csv.DictReader(h)


def write(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)


def score(values):
    return 10*(1+sum(values)/len(values)) if values else None


def signature(quote):
    words=re.findall(r'\w+',quote.lower())
    shingles={tuple(words[i:i+5]) for i in range(max(0,len(words)-4))}
    return shingles,set(re.findall(r'\d+(?:[.,]\d+)*',quote)),len(words)


def near_duplicate(current,previous):
    a,numbers,length=current
    for b,old_numbers,old_length in previous:
        if length<12 or min(length,old_length)/max(length,old_length)<0.8 or numbers!=old_numbers:continue
        if a and len(a&b)/len(a|b)>=0.85:return True
    return False


def operation_eligible(quote,status):
    """Không coi kế hoạch hoặc chỉ ký thỏa thuận là vận hành thực tế."""
    if status in ('planned','mixed_plan_and_actual','not_implemented'):
        return False
    agreement=bool(re.search(r'ký kết|thỏa thuận|thoả thuận|biên bản ghi nhớ',quote,re.I))
    actual=bool(re.search(r'đã triển khai|đã đưa vào|đang vận hành|đang cung cấp|ra mắt|hiện cung cấp|đã tích hợp',quote,re.I))
    if agreement and not actual:
        return False
    return status in ('reported_deployment','reported_result','pilot') or actual


def inputs():
    # Báo cáo trước tin: bản sao nguyên văn từ báo cáo không tạo thêm quan sát báo chí.
    docs=[r for r in read(ROOT/'output/processed/evidence/source_documents.csv') if r['source']!='app_review']
    docs.sort(key=lambda r:(0 if r['source'].endswith('report') else 1,r['source_id']))
    for r in docs:
        yield dict(company=CONFIG['company_mapping'][r['entity']],entity=r['entity'],source='reports' if r['source'].endswith('report') else 'press',origin=r['source'],doc_id=r['source_id'],text=r['text'],date=r['date'],url=r['url'],page=r['page'])
    # Dùng toàn bộ review đã xử lý, không chỉ 500 review của pilot bằng chứng.
    for r in read(ROOT/'output/processed/sentiment/documents.csv'):
        if r['source']=='app_review':
            yield dict(company=CONFIG['company_mapping'][r['entity']],entity=r['entity'],source='reviews',origin=r['platform'],doc_id=r['doc_id'],text=r['text'],date=r['date'],url=r['url'],page='')


def run(output=None):
    out=Path(output) if output is not None else ROOT/'output/legacy/public_text_intermediate'
    out.mkdir(parents=True,exist_ok=True)
    counts=Counter();seen=set();near_seen=defaultdict(list);candidates=[];by_document=defaultdict(list)
    for d in inputs():
        counts[d['source']+':documents']+=1
        text=norm(d['text'])
        for m in re.finditer(r'.+?(?:[.!?;](?=\s+[^\W\d_])|$)',text):
            quote=m.group().strip()
            if len(quote)>1200:
                counts['long_segments_excluded']+=1;continue
            if d['source']!='reviews' and not DIGITAL_CONTEXT.search(quote) and not re.search(r'công nghệ|trung tâm dữ liệu|phân tích dữ liệu|quản trị dữ liệu|(?-i:\bAI\b)',quote,re.I):continue
            if d['source']=='press':
                named={CONFIG['company_mapping'][e] for e,rx in ENTITY_RX.items() if rx.search(quote)}
                if named!={d['company']}:
                    counts['ambiguous_press_sentence_excluded']+=1;continue
            status=stage(quote,d['source']=='reviews')
            if status in ('award_or_recognition','promotion_or_instruction','mixed_plan_and_actual'):
                counts['award_promotion_mixed_excluded']+=1;continue
            if re.search(r'\b20(?:0\d|1\d|2[0-4])\b',quote):
                counts['historical_sentence_excluded']+=1;continue
            matches=[]
            for pillar,indicators in PATTERNS.items():
                if d['source']=='reviews' and pillar!='Khách hàng':continue
                for indicator,rx in indicators.items():
                    if rx.search(quote):
                        if pillar=='Vận hành' and not operation_eligible(quote,status):
                            counts['operation_not_active_excluded']+=1;continue
                        matches.append((pillar,indicator))
            if not matches:continue
            _,evidence=sentence_evidence(quote)
            p=sum(e['sign']>0 for e in evidence);n=sum(e['sign']<0 for e in evidence)
            if not p+n:
                counts['no_sentiment_signal_excluded']+=1;continue
            tone=(p-n)/(p+n)
            # Mỗi quote chỉ thuộc 1 chỉ tiêu/trụ cột để tránh cộng chồng.
            # Ưu tiên cụ thể: dữ liệu > vận hành > chiến lược > công nghệ > khách hàng.
            priority={'Dữ liệu':0,'Vận hành':1,'Chiến lược':2,'Công nghệ':3,'Khách hàng':4}
            pillar,indicator=min(matches,key=lambda x:(priority[x[0]],list(PATTERNS[x[0]]).index(x[1])))
            key=(d['company'],re.sub(r'\W+',' ',quote.lower()).strip())
            if key in seen:
                counts['duplicate_quotes_excluded']+=1;continue
            seen.add(key)
            if d['source']!='reviews':
                sig=signature(quote)
                bucket=near_seen[(d['company'],pillar,indicator)]
                if near_duplicate(sig,bucket):
                    counts['near_duplicate_quotes_excluded']+=1;continue
                bucket.append(sig)
            row=dict(**d,pillar=pillar,indicator=indicator,quote=quote,tone=tone,claim_status=status,other_matches=';'.join(p+':'+i for p,i in matches if (p,i)!=(pillar,indicator)),signal_id=hashlib.sha256(repr(key).encode()).hexdigest()[:24])
            row.pop('text')
            candidates.append(row)
            by_document[(d['company'],pillar,indicator,d['source'],d['doc_id'])].append(tone)
    # Một tài liệu chỉ có một tiếng nói/chỉ tiêu; một báo cáo nhiều trang vẫn là một tài liệu.
    doc_scores=defaultdict(list)
    for (company,pillar,indicator,source,doc),values in by_document.items():
        if source=='reports':doc=doc.rsplit(':',1)[0]
        doc_scores[(company,pillar,indicator,source,doc)].extend(values)
    cells=defaultdict(list)
    for (company,pillar,indicator,source,doc),values in doc_scores.items():
        cells[(company,pillar,indicator,source)].append(sum(values)/len(values))
    # Chỉ so sánh trên ô chỉ tiêu/nhóm nguồn có tín hiệu ở CẢ 5 đơn vị.
    shared={(pillar,indicator,source) for c,pillar,indicator,source in cells if all((company,pillar,indicator,source) in cells for company in COMPANIES)}
    cell_rows=[]
    for (company,pillar,indicator,source),values in sorted(cells.items()):
        cell_rows.append(dict(company=company,pillar=pillar,indicator=indicator,source=source,score_20=round(score(values),4),document_count=len(values),used_in_comparison=(pillar,indicator,source) in shared))
    pillar_rows=[];ranking=[]
    for company in COMPANIES:
        totals=[]
        row={'company':company}
        for pillar,definition in CONFIG['pillars'].items():
            # Cố định số chỉ tiêu và trọng số của chúng giữa các công ty.
            indicator_values=[]
            for indicator in definition['indicators']:
                values=[score(cells[(company,pillar,indicator,s)]) for s in ('reports','press','reviews') if (pillar,indicator,s) in shared]
                if values:indicator_values.append(sum(values)/len(values))
            value=sum(indicator_values)/len(indicator_values) if indicator_values else None
            row[pillar]=round(value,3) if value is not None else ''
            totals.append(value)
            pillar_rows.append(dict(company=company,pillar=pillar,score_20=row[pillar],shared_indicators=len(indicator_values),defined_indicators=len(definition['indicators']),coverage_percent=round(100*len(indicator_values)/len(definition['indicators']),2),status='text_sentiment_proxy' if value is not None else 'insufficient_common_data'))
        row['total_100']=round(sum(totals),3) if all(x is not None for x in totals) else ''
        row['status']='provisional_public_text_ranking' if row['total_100']!='' else 'not_ranked_missing_pillar'
        ranking.append(row)
    ranking.sort(key=lambda r:(r['total_100']=='' , -r['total_100'] if r['total_100']!='' else 0,r['company']))
    previous=None;rank=0
    for index,row in enumerate(ranking,1):
        if row['total_100']!='':
            if row['total_100']!=previous:rank=index
            row['rank']=rank;previous=row['total_100']
        else:row['rank']=''
    write(out/'ranking.csv',ranking,['rank','company',*CONFIG['pillars'],'total_100','status'])
    write(out/'pillar_scores.csv',pillar_rows,list(pillar_rows[0]))
    write(out/'indicator_source_scores.csv',cell_rows,list(cell_rows[0]) if cell_rows else ['status'])
    write(out/'unique_signals.csv',candidates,list(candidates[0]) if candidates else ['status'])
    meta=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),config=CONFIG,audit=dict(counts),unique_signals=len(candidates),common_cells=[list(x) for x in sorted(shared)],formula='10*(1+mean tone), equal indicators, equal source groups inside indicator; only common cells across five companies',limitations='Không phải năng lực số đã xác minh. Exact dedup và near-duplicate Jaccard 5-token>=0.85 với số liệu trùng; chưa gom hoàn toàn cùng sự kiện. Kết quả vẫn chịu thiên lệch nội dung PR và mẫu quan sát.',inputs=['output/processed/evidence/source_documents.csv (nonreview)','output/processed/sentiment/documents.csv (all app reviews)'])
    (out/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# DBI thử nghiệm từ sắc thái văn bản công khai','','VNG (VNZ) bao gồm VNG/ZaloPay theo phạm vi người dùng xác định. Không đồng nhất chỉ tiêu sản phẩm ZaloPay với chỉ tiêu toàn VNG khi diễn giải. Mỗi trụ cột tối đa 20; tổng tối đa 100. Đây là chỉ số proxy sắc thái công khai, không xác nhận năng lực nội bộ.','','| Hạng | Công ty | Khách hàng | Công nghệ | Dữ liệu | Vận hành | Chiến lược | Tổng |','|---|---|---:|---:|---:|---:|---:|---:|']
    for r in ranking:lines.append('| '+' | '.join(str(r[k]) for k in ['rank','company',*CONFIG['pillars'],'total_100'])+' |')
    lines+=['','## Quy tắc công bằng và tránh trùng','','1. Mỗi câu/đoạn chỉ vào một chỉ tiêu và một trụ cột theo thứ tự ưu tiên công khai trong mã nguồn; các nhãn còn lại được lưu other_matches.','2. Quote chuẩn hóa trùng chính xác trong cùng công ty chỉ giữ một lần, kể cả đăng lại ở nguồn khác; báo cáo được ưu tiên làm nguồn gốc. Chưa bảo đảm mọi bài diễn đạt khác về cùng sự kiện đã được gộp.','3. Trung bình tone trong tài liệu, rồi trung bình các tài liệu trong một ô chỉ tiêu/nhóm nguồn. Nhiều bài không tạo thêm điểm cộng.','4. Hai bộ crawl báo chí gộp thành một nhóm press; báo cáo một nhóm reports; review một nhóm reviews. Review chỉ tham gia Khách hàng. Các nhóm có dữ liệu chung được chia đều trong từng chỉ tiêu; các chỉ tiêu có dữ liệu chung được chia đều trong trụ cột.','5. Chỉ dùng cùng tập ô chỉ tiêu/nhóm nguồn cho cả năm công ty. Không tự thay trọng số riêng cho công ty thiếu dữ liệu. Các chỉ tiêu không có dữ liệu chung bị loại cho TẤT CẢ, và độ phủ được báo cáo. Nếu thiếu cả một trụ cột, không tính tổng/xếp hạng thay vì tự gán 0.','6. Score=10*(1+tone trung bình), trong [0,20]. Không có từ cảm xúc không tự nhận 10 điểm; đoạn không có tín hiệu bị loại. Giải thưởng, khuyến mại, câu lẫn kế hoạch/kết quả, tham chiếu trước 2025 bị loại. Kế hoạch vẫn có thể phản ánh sắc thái nhưng không được diễn giải là thành tựu.','','## Giới hạn','','Điểm cao nghĩa là sắc thái tích cực hơn trên các ô quan sát chung, không chứng minh năng lực số tốt hơn. Ngân hàng có nhiều bài vẫn có thể khác phân bố nội dung, nên cân trọng số không loại hết thiên lệch. Công thức và từ điển chưa được kiểm định độc lập; chưa có khoảng tin cậy. Nguồn 2 hiện chỉ là pilot đã lấy toàn văn, không phải toàn kho. Độ phủ thấp hoặc tập ô chung thay đổi làm thứ hạng kém ổn định.','', 'Xem pillar_scores.csv để biết số chỉ tiêu được dùng; indicator_source_scores.csv để xem ô nào bị loại; unique_signals.csv để truy vết từng tín hiệu. Không so sánh điểm giữa hai lần chạy nếu tập ô chung thay đổi.']
    lines+=['','## Vận hành điều chỉnh','','Vận hành bao gồm triển khai dịch vụ số, liên kết và kết nối dịch vụ đã có dấu hiệu hoạt động, bên cạnh tự động hóa/quy trình/hiệu quả. Kế hoạch, chưa triển khai và chỉ ký thỏa thuận không được đưa vào Vận hành. Thí điểm có thể đóng góp sắc thái nhưng không đồng nghĩa triển khai toàn diện; xem claim_status để phân biệt. Tất cả vẫn là tuyên bố công khai, chưa xác nhận độc lập. Không so sánh trực tiếp điểm/tổng với v1 do định nghĩa và tập chỉ tiêu chung thay đổi.','','## Kiểm tra trùng gần','','Với tin/báo cáo: thêm lọc trùng gần theo Jaccard tập 5 token >=0,85, độ dài tương đồng >=0,8 và tập số liệu giống nhau trong cùng công ty/chỉ tiêu. Quote có số liệu mới không bị gộp bởi quy tắc trùng gần. Đây chưa phải nhận diện ngữ nghĩa hoàn chỉnh của cùng sự kiện.','', 'Lượt chạy này: '+str(counts['duplicate_quotes_excluded'])+' quote trùng chính xác và '+str(counts['near_duplicate_quotes_excluded'])+' quote trùng gần bị loại.']
    lines+=['','## Độ phủ và khả năng phân biệt','','| Trụ cột | Chỉ tiêu chung / định nghĩa | Độ phủ | Điểm giữa các công ty |','|---|---:|---:|---|']
    for pillar in CONFIG['pillars']:
        group=[r for r in pillar_rows if r['pillar']==pillar]
        values=[r['score_20'] for r in group if r['score_20']!='']
        distinct=len(set(values))
        lines.append(f"| {pillar} | {group[0]['shared_indicators']}/{group[0]['defined_indicators']} | {group[0]['coverage_percent']}% | {'Chưa phân biệt được' if distinct<2 else 'Có chênh lệch sắc thái'} |")
    op_rows=[r for r in cell_rows if r['pillar']=='Vận hành' and r['used_in_comparison']]
    if op_rows:
        lines+=['','Số tài liệu đóng góp vào ô Vận hành chung: '+', '.join(r['company']+': '+str(r['document_count']) for r in op_rows)+'. Điểm tối đa từ ít bài tích cực không đồng nghĩa vận hành hoàn hảo. Tổng điểm/thứ hạng chỉ để thí điểm; chưa đánh giá độ ổn định khi thay nguồn hoặc bộ quy tắc.']
    (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'unique_signals':len(candidates),'shared_cells':len(shared),'ranking':ranking},ensure_ascii=True,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output/legacy/five_pillars')
    run(parser.parse_args().output)
