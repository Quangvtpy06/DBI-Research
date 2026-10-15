"""DBI bốn trụ cột: trung bình có trọng số trên thang 100 và heatmap."""
import contextlib
import copy
import io
import json
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import score_dbi_public_text as engine

ROOT=Path(__file__).resolve().parent
WEIGHTS={'Công nghệ':40,'Khách hàng':20,'Dữ liệu':30,'Chiến lược':10}
LABELS={1:'Mức cơ bản',2:'Mức đang phát triển',3:'Mức phát triển',4:'Mức nâng cao',5:'Mức dẫn đầu'}


def level(value):
    value=Decimal(str(value))
    if not 0<=value<=100:raise ValueError('Điểm phải trong [0,100]')
    return 1 if value<25 else 2 if value<50 else 3 if value<75 else 4 if value<100 else 5


def readiness(scores,weights=WEIGHTS):
    if set(scores)!=set(weights):raise ValueError('Thiếu/thừa trụ cột')
    if any(Decimal(str(w))<0 for w in weights.values()) or sum(weights.values())<=0:raise ValueError('Trọng số không hợp lệ')
    if any(not 0<=Decimal(str(v))<=100 for v in scores.values()):raise ValueError('Điểm phải trong [0,100]')
    return sum(Decimal(str(scores[p]))*Decimal(str(w)) for p,w in weights.items())/sum(Decimal(str(w)) for w in weights.values())


def run(output=None):
    out=Path(output) if output else ROOT/'output/results'
    diagnostics=out/'diagnostics'
    # Bỏ Vận hành ngay từ bước gán nhãn, không chỉ trừ cột khỏi tổng cũ.
    engine.CONFIG=copy.deepcopy(engine.CONFIG)
    engine.CONFIG['model']='DBI public-text four pillars, v3'
    engine.CONFIG['pillars'].pop('Vận hành',None)
    engine.PATTERNS={p:rules for p,rules in engine.PATTERNS.items() if p in WEIGHTS}
    with contextlib.redirect_stdout(io.StringIO()):engine.run(diagnostics)
    # Bảng trung gian 0–20 không phải bảng R cuối cùng.
    for name in ('ranking.csv','REPORT.md','pillar_scores.csv'):
        (diagnostics/name).unlink(missing_ok=True)
    cells=list(engine.read(diagnostics/'indicator_source_scores.csv'))
    signals=list(engine.read(diagnostics/'unique_signals.csv'))
    # Tính lại từ tín hiệu gốc, tránh mất độ chính xác do CSV điểm làm tròn.
    from collections import defaultdict,Counter
    docs=defaultdict(list)
    for r in signals:
        doc=r['doc_id'].rsplit(':',1)[0] if r['source']=='reports' else r['doc_id']
        docs[(r['company'],r['pillar'],r['indicator'],r['source'],doc)].append(Decimal(r['tone']))
    values=defaultdict(list)
    for (company,pillar,indicator,source,doc),tones in docs.items():values[(company,pillar,indicator,source)].append(sum(tones)/len(tones))
    common={(p,i,s) for c,p,i,s in values if all((company,p,i,s) in values for company in engine.COMPANIES)}
    ranking=[];pillar_rows=[];level_rows=[]
    for company in engine.COMPANIES:
        scores={};row={'company':company}
        for pillar in WEIGHTS:
            indicators=[]
            for indicator in engine.CONFIG['pillars'][pillar]['indicators']:
                source_scores=[]
                for source in ('reports','press','reviews'):
                    if (pillar,indicator,source) in common:
                        tones=values[(company,pillar,indicator,source)]
                        source_scores.append(Decimal(50)*(1+sum(tones)/len(tones)))
                if source_scores:indicators.append(sum(source_scores)/len(source_scores))
            value=sum(indicators)/len(indicators) if indicators else None
            defined=len(engine.CONFIG['pillars'][pillar]['indicators'])
            row[pillar]=round(float(value),4) if value is not None else ''
            if value is not None:scores[pillar]=value
            lv=level(value) if value is not None else ''
            pillar_rows.append(dict(company=company,pillar=pillar,score_100=row[pillar],level=lv,level_label=LABELS.get(lv,''),weight_percent=WEIGHTS[pillar],shared_indicators=len(indicators),defined_indicators=defined,coverage_percent=round(100*len(indicators)/defined,2)))
        r=readiness(scores) if len(scores)==4 else None
        lv=level(r) if r is not None else ''
        row.update(R=round(float(r),4) if r is not None else '',R_exact=str(r) if r is not None else '',level=lv,level_label=LABELS.get(lv,''),status='provisional_public_text_readiness' if r is not None else 'missing_common_pillar')
        ranking.append(row)
    ranking.sort(key=lambda r:(r['R']=='',-Decimal(r['R_exact']) if r['R']!='' else 0,r['company']))
    last=None;rank=0
    for index,row in enumerate(ranking,1):
        if row['R']!='':
            if row['R_exact']!=last:rank=index
            row['rank']=rank;last=row['R_exact']
        else:row['rank']=''
    engine.write(out/'ranking.csv',ranking,['rank','company',*WEIGHTS,'R','R_exact','level','level_label','status'])
    engine.write(out/'pillar_scores.csv',pillar_rows,list(pillar_rows[0]))
    config=dict(model='DBI bốn trụ cột dựa trên sentiment công khai',weights=WEIGHTS,score_scale='0–100 mỗi trụ cột',formula='R=(40*CongNghe+20*KhachHang+30*DuLieu+10*ChienLuoc)/100',thresholds={'1':'0 <= R < 25','2':'25 <= R < 50','3':'50 <= R < 75','4':'75 <= R < 100','5':'R = 100 exactly'},labels=LABELS,notes='Phân mức trên giá trị chưa làm tròn; không chia thêm cho 4; không còn Vận hành ngay từ bước gán nhãn.')
    (out/'method.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    # Heatmap giữ thang màu tuyệt đối 0–100, không min-max theo năm công ty.
    matrix=np.array([[float(r[p]) if r[p]!='' else np.nan for p in WEIGHTS]+[float(r['R']) if r['R']!='' else np.nan] for r in ranking])
    plt.rcParams['font.family']='DejaVu Sans'
    fig,ax=plt.subplots(figsize=(11.8,5.8),layout='constrained')
    image=ax.imshow(np.ma.masked_invalid(matrix),vmin=0,vmax=100,cmap='YlGnBu',aspect='auto')
    ax.set_xticks(range(5),[f'{p}\n({w}%)' for p,w in WEIGHTS.items()]+['Điểm R\n(có trọng số)'])
    ax.set_yticks(range(len(ranking)),[f"{r['rank']}. {r['company']}" for r in ranking])
    ax.tick_params(axis='both',length=0,labelsize=11)
    for i,row in enumerate(ranking):
        for j in range(5):
            value=matrix[i,j]
            text='Thiếu dữ liệu' if np.isnan(value) else f'{value:.2f}\nMức {level(row["R_exact"] if j==4 else value)}'
            ax.text(j,i,text,ha='center',va='center',fontsize=10,color='white' if value>=70 else '#18232e',fontweight='bold' if j==4 else 'normal')
    ax.axvline(3.5,color='white',lw=3)
    ax.set_title('DBI thử nghiệm — Bốn trụ cột và điểm sẵn sàng R',loc='left',fontsize=16,fontweight='bold',pad=20)
    fig.colorbar(image,ax=ax,label='Điểm trên thang 100',shrink=.85)
    fig.supxlabel('Mức 1: <25   •   Mức 2: 25–<50   •   Mức 3: 50–<75   •   Mức 4: 75–<100   •   Mức 5: đúng 100\nChỉ số từ sắc thái công khai; mức 5 không đồng nghĩa năng lực nội bộ hoàn hảo.',fontsize=9)
    fig.savefig(out/'heatmap.png',dpi=200)
    fig.savefig(out/'heatmap.svg')
    plt.close(fig)
    lines=['# DBI bốn trụ cột — điểm sẵn sàng R','','Đã bỏ Vận hành ngay từ bước gán nhãn và chạy lại trên dữ liệu hiện có. Mỗi trụ cột dùng thang 0–100. R là trung bình có trọng số, không chia thêm cho 4.','','R = (Công nghệ × 40 + Khách hàng × 20 + Dữ liệu × 30 + Chiến lược × 10) / 100','','| Hạng | Công ty | Công nghệ | Khách hàng | Dữ liệu | Chiến lược | R | Phân mức |','|---|---|---:|---:|---:|---:|---:|---|']
    for row in ranking:
        lines.append('| '+str(row['rank'])+' | '+row['company']+' | '+' | '.join(f"{row[p]:.2f}" if row[p]!='' else 'NA' for p in WEIGHTS)+' | '+(f"{row['R']:.2f}" if row['R']!='' else 'NA')+' | '+str(row['level'])+' — '+row['level_label']+' |')
    lines+=['','![Biểu đồ nhiệt](heatmap.png)','','Ngưỡng: Mức 1 cơ bản [0,25); Mức 2 đang phát triển [25,50); Mức 3 phát triển [50,75); Mức 4 nâng cao [75,100); Mức 5 dẫn đầu đúng 100. Phân mức theo số chưa làm tròn.','','## Độ phủ chung','','| Trụ cột | Chỉ tiêu dùng / định nghĩa | Độ phủ |','|---|---:|---:|']
    for p in WEIGHTS:
        r=next(x for x in pillar_rows if x['pillar']==p)
        lines.append(f"| {p} | {r['shared_indicators']}/{r['defined_indicators']} | {r['coverage_percent']}% |")
    lines+=['','## Giới hạn và kiểm soát','','Điểm phản ánh sắc thái văn bản công khai, không phải kiểm định năng lực nội bộ. Các mức 1–5 là quy ước dự án do người dùng xác định. Điểm trụ cột bằng 100 có thể do toàn bộ tín hiệu quan sát đều dương, không chứng minh năng lực toàn diện.','','Giữ quy tắc một quote/chỉ tiêu/trụ cột, loại trùng chính xác và trùng gần, trung bình theo tài liệu và chia đều các nhóm nguồn trong từng chỉ tiêu; chỉ dùng tập ô chung cho năm công ty. Không có dữ liệu không tự nhận 0 hoặc 50. Xem diagnostics/unique_signals.csv để truy vết. Review chỉ dùng cho Khách hàng; VNG bao gồm ZaloPay. Nguồn 2 vẫn là pilot đã có toàn văn, chưa phải toàn kho.','','Kết quả cùng Mức 4 vẫn có thể khác hạng theo R; không ép năm công ty vào đủ năm mức. Thiếu dữ liệu hoặc điểm tập trung gần trần có thể làm thứ hạng kém ổn định. Giữ nguyên các output phiên bản trước.']
    (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    verification=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),companies=len(ranking),unique_signals=len(signals),no_operation_signals=all(r['pillar']!='Vận hành' for r in signals),weights_total=sum(WEIGHTS.values()),source_metadata_sha256=__import__('hashlib').sha256((diagnostics/'metadata.json').read_bytes()).hexdigest())
    assert verification['no_operation_signals'] and verification['weights_total']==100
    assert all(0<=r['R']<=100 and level(r['R_exact'])==r['level'] for r in ranking if r['R']!='')
    (out/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    print(json.dumps(ranking,ensure_ascii=True,indent=2))


if __name__=='__main__':run()
