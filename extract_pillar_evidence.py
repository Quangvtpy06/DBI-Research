"""Trích ứng viên bằng chứng DBI có truy vết; không tính điểm/xếp hạng."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sentiment_module import sentence_evidence, label, DIGITAL_CONTEXT

ROOT = Path(__file__).resolve().parent
TAXONOMY = json.loads((ROOT/'evidence_taxonomy.json').read_text(encoding='utf-8'))
RULES = {p: {i:re.compile(r'(?<!\w)(?:'+rx+r')(?!\w)',re.I) for i,rx in item['indicators'].items()} for p,item in TAXONOMY['pillars'].items()}
ALIASES = {'ZaloPay':r'zalopay|zalo pay', 'VPBank':r'vpbank|vpbank neo', 'VCB':r'vietcombank|vcb|digibank', 'HDBank':r'hdbank|hd bank', 'ACB':r'acb|á châu|acb one', 'VNG':r'vng|vnz|greennode|zalo(?!pay| pay)'}
ENTITY_RX = {k:re.compile(r'(?<!\w)(?:'+v+r')(?!\w)',re.I) for k,v in ALIASES.items()}
TICKERS = {'VNG':'VNG','VNZ':'VNG','VPB':'VPBank','VCB':'VCB','HDB':'HDBank','ACB':'ACB'}
FUTURE = re.compile(r'\bsẽ\b|dự kiến|đặt mục tiêu|mục tiêu|định hướng|kế hoạch|hướng tới|phấn đấu',re.I)
NOT_DONE = re.compile(r'chưa (?:triển khai|hoàn thành|đưa vào|vận hành|áp dụng)|không (?:triển khai|áp dụng)',re.I)
PILOT = re.compile(r'thí điểm|thử nghiệm|pilot|proof.of.concept',re.I)
DEPLOYED = re.compile(r'đã triển khai|triển khai|đã đưa vào|đang vận hành|đã vận hành|đưa vào vận hành|ra mắt|đã áp dụng|hoàn thành|được áp dụng|đã tích hợp|đã sử dụng',re.I)
RESULT = re.compile(r'đạt|đã xử lý|tăng|giảm|chiếm|tiết kiệm|rút ngắn|phục vụ|thực hiện|ghi nhận',re.I)
INCIDENT = re.compile(r'bị tấn công|xảy ra sự cố|bị gián đoạn|bị rò rỉ|bị lộ|sập hệ thống',re.I)
PREVENT = re.compile(r'cảnh báo|phòng chống|phòng ngừa|ngăn chặn|phòng tránh',re.I)
QUANTITY = re.compile(r'(?<!\w)(?:[<>~≈]\s*)?\d+(?:[.,]\d+)*(?:\s*(?:triệu tỷ|nghìn tỷ|triệu|nghìn|tỷ))?\s*(?:%|đồng|VND|USD|khách hàng|người dùng|nhân sự|nhân viên|giao dịch|giây|phút|giờ|ngày|quy trình|sản phẩm|dịch vụ|tài khoản)',re.I)


def norm(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFC',text or '')).strip()


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as handle:
        yield from csv.DictReader(handle)


def write_csv(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)


def stage(text,review=False):
    if review:
        return 'user_experience'
    if NOT_DONE.search(text):
        return 'not_implemented'
    if PREVENT.search(text):
        return 'prevention_or_warning'
    if re.search(r'giải thưởng|vinh danh|hội đồng bình chọn',text,re.I):
        return 'award_or_recognition'
    if re.search(r'voucher|mã ưu đãi|khuyến mại|khuyến mãi|mã mỗi ngày|đối tượng.*ưu đãi|sponsorship|^thực hiện\s+0?1\s+giao dịch',text,re.I):
        return 'promotion_or_instruction'
    if INCIDENT.search(text):
        return 'reported_incident'
    planned, pilot = bool(FUTURE.search(text)), bool(PILOT.search(text))
    # Không coi "dự kiến triển khai/đạt 90%" là kết quả hiện có.
    actual_text=[]
    for clause in re.split(r';|,|\bvà (?=đặt mục tiêu|dự kiến|sẽ)',text,flags=re.I):
        future=FUTURE.search(clause)
        actual_text.append(clause[:future.start()] if future else clause)
    actual_text=' '.join(actual_text)
    actual = bool(DEPLOYED.search(actual_text) or (QUANTITY.search(actual_text) and RESULT.search(actual_text)))
    if planned and actual:
        return 'mixed_plan_and_actual'
    if planned:
        return 'planned'
    if pilot:
        return 'pilot'
    if QUANTITY.search(text) and RESULT.search(text):
        return 'reported_result'
    if DEPLOYED.search(text):
        return 'reported_deployment'
    return 'mention_only'


def matched_rules(text,review=False):
    if not review and not DIGITAL_CONTEXT.search(text) and not re.search(r'chuyển đổi số|công nghệ|trung tâm dữ liệu|(?-i:\bAI\b)',text,re.I):
        return []
    matches=[]
    for pillar,indicators in RULES.items():
        # Review không chứng minh chiến lược, công nghệ nội bộ hoặc hiệu quả tổ chức.
        if review and pillar not in ('P3','P5'):
            continue
        for indicator,rx in indicators.items():
            hits=list(dict.fromkeys(m.group() for m in rx.finditer(text)))
            if hits:
                # Lượt giao dịch/người dùng trong review không phải chỉ tiêu quy mô.
                if review and indicator=='digital_adoption':
                    continue
                if indicator=='digital_adoption' and not re.search(r'số lượng|quy mô|triệu|nghìn|tỷ lệ|giao dịch|người dùng|onboarding|khách hàng số|khách hàng sử dụng',text,re.I):
                    continue
                matches.append((pillar,indicator,hits))
    return matches


def review_sample(limit):
    groups=defaultdict(list)
    path=ROOT/'output/raw/app_reviews/reviews_2025_to_now.csv'
    for r in read_csv(path):
        if not norm(r.get('content','')):
            continue
        key=(r['entity'],r['platform'],r['rating'])
        groups[key].append(r)
    rng=random.Random(20261015)
    for group in groups.values():
        group.sort(key=lambda r:r['review_id']);rng.shuffle(group)
    result=[]
    for entity in sorted({k[0] for k in groups}):
        keys=sorted(k for k in groups if k[0]==entity)
        chosen=[]
        while len(chosen)<limit and any(groups[k] for k in keys):
            for k in keys:
                if groups[k] and len(chosen)<limit:
                    chosen.append(groups[k].pop())
        result.extend(chosen)
    return result


def documents(review_limit,source2):
    for r in read_csv(source2):
        if r['fetch_status']!='success' or str(r.get('has_fulltext','')).lower()!='true':
            continue
        yield dict(entity=TICKERS[r['ticker']],source='press_crawl_2',source_id=r['article_id'],text=r['text'],title=r['title'],date=r['date'],page='',url=r['publisher_url'],input_path=str(source2.relative_to(ROOT)),scope='article_entity_unverified')
    path=ROOT/'output/raw/press_1/press_events_2025_to_now.csv'
    for r in read_csv(path):
        if not norm(r.get('content','')):
            continue
        yield dict(entity=r['entity'],source='press_crawl_1',source_id=r['content_hash'],text=r['content'],title=r['title'],date=r['published_date'],page='',url=r['url'],input_path=str(path.relative_to(ROOT)),scope='article_entity_unverified')
    sources={r['id']:r for r in json.loads((ROOT/'report_sources.json').read_text(encoding='utf-8'))['documents']}
    for path in sorted((ROOT/'output/raw/reports/text').glob('*.json')):
        meta=sources[path.stem]
        for r in json.loads(path.read_text(encoding='utf-8-sig')):
            yield dict(entity=TICKERS[meta['symbol']],source='annual_report' if meta['kind']=='annual' else 'financial_report',source_id=f"{path.stem}:{r['pdf_page']}",text=r.get('text',''),title=meta['period'],date=meta['period'],page=r['pdf_page'],url=meta['url'],input_path=str(path.relative_to(ROOT)),scope='group_report')
    for r in review_sample(review_limit):
        yield dict(entity=r['entity'],source='app_review',source_id=r['platform']+':'+r['review_id'],text=r['content'],title='',date=r['review_date'],page='',url='',input_path='output/raw/app_reviews/reviews_2025_to_now.csv',scope='product_user_claim')


def extract_document(doc):
    text=norm(doc['text'])
    doc_id=digest(doc['source']+'|'+doc['source_id'])
    review=doc['source']=='app_review'
    output=[]
    # Không tách dấu chấm thập phân; quote luôn là đoạn con của văn bản chuẩn hóa.
    for match in re.finditer(r'.+?(?:[.!?;](?=\s+[^\W\d_])|$)',text):
        quote=match.group().strip()
        rules=matched_rules(quote,review)
        if not rules:
            continue
        named=[entity for entity,rx in ENTITY_RX.items() if rx.search(quote)]
        subject=doc['entity']
        if subject=='VNG' and 'ZaloPay' in named:
            subject='ZaloPay'
        flags=[]
        if not review:
            if len(named)>1:
                flags.append('multiple_entities')
            if subject not in named and doc['scope']!='group_report':
                flags.append('subject_not_explicit')
            elif subject not in named:
                flags.append('subject_inherited_from_report')
            if subject=='VNG':
                flags.append('group_not_zalopay')
            if named and subject not in named:
                flags.append('subject_conflicts_with_named_entity')
        if doc['scope']=='group_report':
            flags.append('verify_pdf_and_scope')
        if len(quote)>1200:
            flags.append('long_or_ocr_segment')
        if re.search(r'\d{2}[-/]\d{2}[-/]20\d{2}|tin liên quan|tin cùng chuyên mục|tin nóng',quote,re.I):
            flags.append('possible_related_news_noise')
        years=sorted(set(re.findall(r'\b20\d{2}\b',quote)))
        if any(int(year)<2025 for year in years):
            flags.append('contains_pre2025_reference')
        if any(int(year)<2025 for year in re.findall(r'\b20\d{2}\b',doc['title'])):
            flags.append('title_references_pre2025')
        status=stage(quote,review)
        if status in ('mention_only','mixed_plan_and_actual'):
            flags.append('claim_status_needs_review')
        _,sentiment=sentence_evidence(quote)
        p=sum(e['sign']>0 for e in sentiment);n=sum(e['sign']<0 for e in sentiment)
        tone=(p-n)/(p+n) if p+n else 0
        for pillar,indicator,hits in rules:
            cluster=digest(subject+'|'+indicator+'|'+quote.lower())
            output.append(dict(evidence_id=digest(doc_id+'|'+str(match.start())+'|'+indicator),doc_id=doc_id,entity=subject,tagged_entity=doc['entity'],pillar=pillar,pillar_label=TAXONOMY['pillars'][pillar]['label'],indicator=indicator,claim_status=status,quote=quote,matched_terms=';'.join(hits),numbers_raw=json.dumps(QUANTITY.findall(quote),ensure_ascii=False),explicit_years=';'.join(years),sentiment=label(tone,0.1) if p+n else 'NoEvidence',sentiment_mixed=bool(p and n),source=doc['source'],source_id=doc['source_id'],date_or_period=doc['date'],pdf_page=doc['page'],url=doc['url'],input_path=doc['input_path'],scope=doc['scope'],review_flags=';'.join(flags),cluster_id=cluster,human_decision='',human_subject='',human_stage='',human_note=''))
    return {**doc,'doc_id':doc_id,'text':text},output


def run(output,review_limit,source2):
    output.mkdir(parents=True,exist_ok=True)
    docs=[];evidence=[];seen=set();audit=Counter()
    for doc in documents(review_limit,source2):
        audit[doc['source']+':input']+=1
        if not norm(doc['text']):
            audit[doc['source']+':empty']+=1;continue
        dedup=(doc['entity'],doc['source'],doc['source_id'])
        if dedup in seen:
            audit[doc['source']+':duplicate_id']+=1;continue
        seen.add(dedup)
        record,candidates=extract_document(doc)
        docs.append(record);evidence.extend(candidates)
    assert evidence,'Không có ứng viên bằng chứng'
    counts=Counter(r['cluster_id'] for r in evidence)
    for r in evidence:
        r['exact_cluster_size']=counts[r['cluster_id']]
    summary=[]
    for entity in ('ZaloPay','VPBank','VCB','HDBank','ACB','VNG'):
        for pillar,item in TAXONOMY['pillars'].items():
            subset=[r for r in evidence if r['entity']==entity and r['pillar']==pillar]
            unique=len({r['cluster_id'] for r in subset})
            summary.append(dict(entity=entity,pillar=pillar,pillar_label=item['label'],candidate_rows=len(subset),unique_quote_indicator_clusters=unique,documents=len({r['doc_id'] for r in subset}),sources=';'.join(sorted({r['source'] for r in subset})),claim_statuses=json.dumps(Counter(r['claim_status'] for r in subset),ensure_ascii=False),coverage_status='has_candidates' if subset else 'no_candidate_not_zero_capability'))
    write_csv(output/'evidence_candidates.csv',evidence,list(evidence[0]))
    write_csv(output/'source_documents.csv',docs,list(docs[0]))
    write_csv(output/'pillar_coverage.csv',summary,list(summary[0]))
    # Mẫu duyệt ưu tiên kế hoạch/kết quả/triển khai và phủ các nguồn, trụ cột.
    groups=defaultdict(list)
    for row in evidence:
        groups[(row['entity'],row['pillar'],row['source'])].append(row)
    sample=[]
    for key,group in sorted(groups.items()):
        order={'reported_result':0,'reported_deployment':1,'pilot':2,'planned':3,'user_experience':4}
        group.sort(key=lambda r:(order.get(r['claim_status'],5),len(r['review_flags']),len(r['quote']),r['evidence_id']))
        sample.extend(group[:2])
    write_csv(output/'annotation_sample.csv',sample,list(evidence[0]))
    excluded={'multiple_entities','subject_not_explicit','subject_conflicts_with_named_entity','group_not_zalopay','long_or_ocr_segment','possible_related_news_noise','contains_pre2025_reference','title_references_pre2025'}
    shortlist=[];clusters=set()
    for r in evidence:
        if r['claim_status'] in ('mention_only','mixed_plan_and_actual','award_or_recognition','promotion_or_instruction') or excluded.intersection(r['review_flags'].split(';')) or r['cluster_id'] in clusters:
            continue
        clusters.add(r['cluster_id']);shortlist.append(r)
    write_csv(output/'review_shortlist.csv',shortlist,list(evidence[0]))
    metadata=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),taxonomy=TAXONOMY,source2_path=str(source2.relative_to(ROOT)),source2_note='Chỉ pilot fulltext đã đạt, chưa phải toàn bộ kho nguồn 2',review_limit_per_entity=review_limit,audit=dict(audit),documents=len(docs),candidate_rows=len(evidence),unique_clusters=len(counts),annotation_sample=len(sample),review_shortlist=len(shortlist),validation='Rule-based candidates, chưa có nhãn độc lập; chưa có điểm DBI',dedup='Cụm chính xác theo chủ thể/chỉ tiêu/quote; chưa gom near-duplicate hay sự kiện',input_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in {ROOT/d['input_path'] for d in docs}|{ROOT/'evidence_taxonomy.json'}})
    (output/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Thí điểm trích xuất bằng chứng theo trụ cột DBI','',f"Đã đọc {len(docs):,} đơn vị tài liệu; trích {len(evidence):,} ứng viên, {len(counts):,} cụm quote/chỉ tiêu chính xác. Mẫu duyệt {len(sample)} dòng.",'','Khung 5 trụ cột là đề xuất pilot, chưa phải chuẩn DBI chính thức. Mỗi dòng là ứng viên chưa được con người xác nhận. Số dòng/cụm không phải điểm hoặc mức trưởng thành. Một quote có thể khớp nhiều chỉ tiêu.','','| Đơn vị | P1 | P2 | P3 | P4 | P5 |','|---|---:|---:|---:|---:|---:|']
    for entity in ('ZaloPay','VPBank','VCB','HDBank','ACB','VNG'):
        vals=[str(next(r['documents'] for r in summary if r['entity']==entity and r['pillar']==p)) for p in TAXONOMY['pillars']]
        lines.append('| '+entity+' | '+' | '.join(vals)+' |')
    lines+=['','Bảng đếm số đơn vị tài liệu có ứng viên ở từng trụ cột. Với báo cáo, đơn vị kỹ thuật là trang; các trang cùng báo cáo không độc lập. Với review là mẫu tối đa '+str(review_limit)+' review/ứng dụng, cân bằng luân phiên platform/rating; không đại diện tỷ lệ khách hàng.','','## Đọc kết quả','','- evidence_candidates.csv: quote, nguồn, URL/trang, trạng thái, chủ thể, chỉ tiêu, số liệu nguyên văn và cờ cần duyệt. numbers_raw chưa được chuẩn hóa và không được tự dùng làm KPI.','- source_documents.csv: văn bản nguồn chuẩn hóa khoảng trắng để đối chiếu quote; pdf_page tính từ 1. date_or_period là ngày đăng hoặc kỳ báo cáo, chưa phải ngày sự kiện.','- annotation_sample.csv: duyệt accept/reject/unclear, sửa chủ thể/trạng thái/chỉ tiêu; nên có người thứ hai kiểm tra độc lập.','- pillar_coverage.csv: độ phủ ứng viên, không phải xếp hạng. VNG giữ riêng; chỉ gắn ZaloPay khi quote nêu rõ.','','## Kết luận thí điểm','','Có thể tiếp tục xây bộ trích xuất và bộ nhãn chuẩn. Chưa đủ điều kiện tổng hợp DBI: cần chốt taxonomy với chuyên gia, đo precision/recall trên tập độc lập (có cả đoạn không được trích), kiểm tra đúng chủ thể và thời gian, tách kế hoạch/kết quả, kiểm tra OCR/PDF, chuẩn hóa KPI và gom sự kiện giữa nguồn. Không biến không có ứng viên thành điểm 0. Sentiment chỉ mô tả giọng điệu, không xác nhận năng lực hay tính đúng của tuyên bố.','', 'Các cờ multiple_entities, subject_not_explicit, group_not_zalopay và long_or_ocr_segment cần ưu tiên duyệt. reported_result/ reported_deployment vẫn là điều tài liệu tuyên bố; chưa chứng minh độc lập. Câu có cả kế hoạch và kết quả được giữ mixed_plan_and_actual thay vì chấm là thành tựu.','', 'Không tự mở rộng crawl hoặc ghi đè sentiment/pilot cũ. Nguồn 2 chỉ sử dụng các bài thành công trong pilot 250 bài.']
    lines+=['','## Danh sách ưu tiên và phát hiện','',f'review_shortlist.csv có {len(shortlist)} dòng ưu tiên duyệt sau khi loại một số cờ rủi ro và gộp trùng chính xác. Đây vẫn là ứng viên, không phải bằng chứng được chấp nhận. Mẫu annotation_sample.csv có '+str(len(sample))+' dòng; chạy verify_pillar_evidence.py để tạo thêm negative_control_sample.csv rà soát bỏ sót.','','Nguồn đầu vào thực tế: 233 bài nguồn 2 đạt kiểm tra; 14 bài nguồn 1 có content (3 dòng còn lại không có content nên không dùng tiêu đề thay toàn văn); 721 trang BCTN không rỗng và 410 trang BCTC; 500 review (100/ứng dụng). Không phải 1.878 tài liệu độc lập vì báo cáo được chia trang.','','Pilot chưa tìm thấy ứng viên P4 gắn rõ với ZaloPay. Các bằng chứng VNG không tự bù cho khoảng trống này; cần đọc bổ sung/chỉnh quy tắc và kiểm định trước khi kết luận.','','Ví dụ ứng viên từ nguồn 2 (chưa xác minh sự thật hoặc kỳ KPI): ACB nêu hơn 1.000 nhân sự công nghệ, khoảng 8% lao động; HDBank nêu hơn 97% giao dịch cá nhân trên nền tảng số; ZaloPay nêu phục vụ trên 16 triệu người dùng. Xem quote, URL và date_or_period trong evidence_candidates.csv trước khi sử dụng. Những tỷ lệ khác nhau giữa bài và báo cáo có thể khác kỳ/phạm vi, cần chuẩn hóa thay vì tự chọn số lớn nhất.']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:metadata[k] for k in ('documents','candidate_rows','unique_clusters','annotation_sample','audit')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output/processed/evidence')
    parser.add_argument('--reviews-per-entity',type=int,default=100)
    parser.add_argument('--source2',type=Path,default=ROOT/'output/processed/press_2_fulltext/enriched_news.csv')
    args=parser.parse_args()
    if args.reviews_per_entity<1:parser.error('reviews-per-entity phải >=1')
    run(args.output,args.reviews_per_entity,args.source2.resolve())
