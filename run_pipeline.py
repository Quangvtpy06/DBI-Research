"""Pipeline DBI: dữ liệu hiện có → toàn văn → sentiment → bằng chứng → R."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/'output'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh',action='store_true',help='Crawl lại review, tin và báo cáo; cần mạng, có thể mất nhiều thời gian')
    parser.add_argument('--enrich-source2',action='store_true',help='Tải thêm toàn văn từ danh sách nguồn 2 hiện có')
    parser.add_argument('--per-company',type=int,default=50,help='Số bài/đơn vị khi tải toàn văn; mặc định pilot 50')
    parser.add_argument('--skip-sentiment',action='store_true',help='Dùng sentiment đã có sau khi kiểm tra đường dẫn')
    args=parser.parse_args(argv)
    OUTPUT.mkdir(exist_ok=True)
    lock=OUTPUT/'.pipeline.lock'
    try:
        handle=lock.open('x',encoding='utf-8');handle.write(str(__import__('os').getpid()));handle.close()
    except FileExistsError:
        print('Pipeline đang chạy hoặc còn khóa từ lần bị ngắt: output/.pipeline.lock',flush=True);return 2
    started=datetime.now(timezone.utc).isoformat();stages=[]
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    logs=OUTPUT/'logs'/run_id;logs.mkdir(parents=True,exist_ok=True)
    status=dict(run_id=run_id,started_at_utc=started,status='running',stages=stages,mode='refresh' if args.refresh else 'existing_data',source2_limit=args.per_company)
    def save():
        tmp=OUTPUT/'pipeline_status.json.tmp';tmp.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(OUTPUT/'pipeline_status.json')
    def step(name,script,*arguments):
        item=dict(name=name,status='running',started_at_utc=datetime.now(timezone.utc).isoformat());stages.append(item);save()
        print(f'Bắt đầu: {name}',flush=True)
        begin=time.monotonic()
        with (logs/(str(len(stages)).zfill(2)+'.log')).open('w',encoding='utf-8') as log:
            process=subprocess.run([sys.executable,'-X','utf8',str(ROOT/script),*map(str,arguments)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        item.update(status='completed' if process.returncode==0 else 'failed',elapsed_seconds=round(time.monotonic()-begin,2),log=str((logs/(str(len(stages)).zfill(2)+'.log')).relative_to(ROOT)))
        save()
        if process.returncode:raise RuntimeError(f'Lỗi bước {name}; xem {item["log"]}')
        print(f'Hoàn thành: {name} ({item["elapsed_seconds"]}s)',flush=True)
    try:
        save()
        if args.refresh:
            step('Thu thập review','crawl_app_reviews.py','--output',OUTPUT/'raw/app_reviews')
            step('Thu thập tin nguồn 1','crawl_press_events.py','--output',OUTPUT/'raw/press_1')
            step('Tải và trích báo cáo','Crawl_Annual_Report_5_company.py','--output',OUTPUT/'raw/reports')
            step('Thu thập RSS nguồn 2','crawl_events_company_p2/bank_project/collect.py','--skip-fulltext')
        if args.enrich_source2 or args.refresh:
            source=OUTPUT/'raw/press_2/raw_news.csv'
            if not source.exists():source=OUTPUT/'raw/press_2/clean_news.csv'
            step('Bổ sung toàn văn nguồn 2','crawl_events_company_p2/bank_project/enrich_fulltext.py','--input',source,'--output',OUTPUT/'processed/press_2_fulltext','--per-company',args.per_company,'--retry-failed')
        fulltext=OUTPUT/'processed/press_2_fulltext/enriched_news.csv'
        if not fulltext.exists():raise FileNotFoundError('Thiếu nguồn 2 toàn văn; chạy với --enrich-source2')
        step('Làm sạch nguồn 2','crawl_events_company_p2/bank_project/analyze.py','--input',fulltext,'--output',OUTPUT/'processed/press_2_fulltext/analyzed')
        if not args.skip_sentiment:step('Phân tích sentiment','sentiment_module.py')
        elif not (OUTPUT/'processed/sentiment/documents.csv').exists():raise FileNotFoundError('Chưa có sentiment để bỏ qua bước này')
        step('Trích xuất ứng viên bằng chứng','extract_pillar_evidence.py')
        step('Kiểm tra truy vết','verify_pillar_evidence.py')
        step('Tính R bốn trụ cột và heatmap','score_dbi_four_pillars.py')
        status.update(status='completed',finished_at_utc=datetime.now(timezone.utc).isoformat())
        result=OUTPUT/'results/ranking.csv';status['ranking_sha256']=hashlib.sha256(result.read_bytes()).hexdigest()
        # Chụp gói kết quả nhỏ sau khi hoàn tất; app đọc bộ này, không đọc dở lúc pipeline chạy.
        import shutil
        published=OUTPUT/'published'
        snapshot=published/'runs'/run_id
        snapshot.mkdir(parents=True,exist_ok=True)
        for name in ('ranking.csv','pillar_scores.csv','method.json','verification.json','heatmap.png','heatmap.svg','REPORT.md'):
            shutil.copy2(OUTPUT/'results'/name,snapshot/name)
        for name in ('unique_signals.csv','indicator_source_scores.csv','metadata.json'):
            shutil.copy2(OUTPUT/'results/diagnostics'/name,snapshot/name)
        (snapshot/'run.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
        # Công bố con trỏ nguyên tử sau khi gói dữ liệu đã hoàn chỉnh.
        pointer=published/'current.json.tmp'
        pointer.write_text(json.dumps({'run_id':run_id,'path':'runs/'+run_id}),encoding='utf-8')
        pointer.replace(published/'current.json')
        save();print('Pipeline hoàn tất. Kết quả: output/results; app: output/published',flush=True);return 0
    except (OSError,RuntimeError) as exc:
        status.update(status='failed',error=str(exc),finished_at_utc=datetime.now(timezone.utc).isoformat());save();print(str(exc),file=sys.stderr);return 1
    finally:
        lock.unlink(missing_ok=True)


if __name__=='__main__':raise SystemExit(main())
