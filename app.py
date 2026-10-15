"""Streamlit DBI Research — dữ liệu công khai, bốn trụ cột, tiếng Việt."""
import html
import json
import os
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/'output'
PUBLISHED=OUTPUT/'published'
try:
    current=json.loads((PUBLISHED/'current.json').read_text(encoding='utf-8'))
    active=(PUBLISHED/current['path']).resolve()
    if PUBLISHED.resolve() in active.parents and active.is_dir():PUBLISHED=active
except (OSError,KeyError,json.JSONDecodeError):
    pass
PILLARS=['Công nghệ','Khách hàng','Dữ liệu','Chiến lược']
WEIGHTS=[40,20,30,10]
SOURCE_LABELS={'reports':'Báo cáo công khai','press':'Báo chí & sự kiện','reviews':'Review ứng dụng'}
INDICATORS={'ha_tang':'Hạ tầng công nghệ','ket_noi':'Kết nối hệ thống','an_toan':'An toàn và xác thực','trai_nghiem':'Trải nghiệm ứng dụng','ho_tro':'Hỗ trợ khách hàng','tiep_can':'Tiếp cận dịch vụ số','nen_tang_du_lieu':'Nền tảng dữ liệu','quan_tri_du_lieu':'Quản trị dữ liệu','ung_dung_du_lieu':'Ứng dụng dữ liệu & AI','dinh_huong':'Định hướng số','quan_tri':'Quản trị chuyển đổi số','nguon_luc':'Nguồn lực số'}

st.set_page_config(page_title='DBI Research · Xếp hạng chuyển đổi số',page_icon='◈',layout='wide',initial_sidebar_state='auto')
st.markdown('''<style>
:root{--ink:#152238;--muted:#526079;--blue:#2563eb;--line:#e2e8f0;--surface:#ffffff}
.stApp{background:#f8fafc;color:var(--ink)}
[data-testid="stSidebar"]{background:white;border-right:1px solid var(--line)}
.block-container{max-width:1360px;padding-top:2.5rem;padding-bottom:3rem}
h1,h2,h3{letter-spacing:-.035em;color:var(--ink)}h1{font-size:2.65rem!important;font-weight:750!important}
p,li{line-height:1.7} [data-testid="stCaptionContainer"]{color:var(--muted)}
[data-testid="stMetric"]{background:white;border:1px solid var(--line);border-radius:14px;padding:20px}
[data-testid="stMetricValue"]{font-size:1.8rem;font-weight:650;color:var(--ink)}
[data-testid="stMetricLabel"]{color:var(--muted)}
[data-testid="stDataFrame"],[data-testid="stPlotlyChart"]{border:1px solid var(--line);border-radius:14px;overflow:hidden;background:white}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.13em;color:#2563eb;margin-bottom:12px;text-transform:uppercase}
.intro{max-width:850px;color:#526079;font-size:16px;margin-top:4px;margin-bottom:24px}
.brand{display:flex;align-items:center;gap:12px;margin:4px 0 28px}.brand-mark{background:#2563eb;color:white;border-radius:11px;padding:11px;font-size:15px;font-weight:800;letter-spacing:.04em}.brand-name{font-size:18px;font-weight:700}.brand-sub{color:#526079;font-size:12px}
.note{border:1px solid #dbeafe;background:#eff6ff;border-radius:12px;padding:16px 20px;color:#25446f;font-size:14px;margin:20px 0}
.step{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:18px;margin-bottom:12px}
.footer{margin-top:32px;padding-top:18px;border-top:1px solid #e2e8f0;color:#526079;font-size:12px}
button:focus-visible,a:focus-visible{outline:3px solid #2563eb!important;outline-offset:3px!important}
@media(max-width:640px){.block-container{padding:1.25rem 1rem}h1{font-size:1.95rem!important}[data-testid="stMetric"]{padding:12px}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>''',unsafe_allow_html=True)


def read_json(path,default=None):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError):return default if default is not None else {}


@st.cache_data(show_spinner=False)
def load_csv(path,stamp):
    return pd.read_csv(path,encoding='utf-8-sig')


def frame(path):
    if not path.exists():return pd.DataFrame()
    return load_csv(str(path),path.stat().st_mtime_ns)


def start_pipeline():
    if (OUTPUT/'.pipeline.lock').exists():return False
    (OUTPUT/'logs').mkdir(parents=True,exist_ok=True)
    with (OUTPUT/'logs/app_launch.log').open('a',encoding='utf-8') as log:
        subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'run_pipeline.py')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return True


def header(kicker,title,description):
    st.markdown(f'<div class="eyebrow">{html.escape(kicker)}</div>',unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="intro">{html.escape(description)}</p>',unsafe_allow_html=True)


def heatmap(rows):
    columns=PILLARS+['R']
    values=rows[columns].to_numpy(dtype=float)
    labels=[[f'{v:.2f}' for v in row] for row in values]
    fig=go.Figure(go.Heatmap(z=values,x=[f'{p}<br>{w}%' for p,w in zip(PILLARS,WEIGHTS)]+['Điểm R'],y=rows['company'].tolist(),zmin=0,zmax=100,colorscale=[[0,'#f0f9ff'],[.3,'#cceef0'],[.55,'#80c6ce'],[.75,'#3b8fa8'],[1,'#163d70']],text=labels,texttemplate='%{text}',hovertemplate='%{y}<br>%{x}: %{z:.2f}/100<extra></extra>',colorbar=dict(title='Điểm',thickness=10),xgap=3,ygap=3))
    fig.update_layout(height=max(300,70*len(rows)+120),margin=dict(l=12,r=15,t=25,b=25),paper_bgcolor='white',plot_bgcolor='white',font=dict(family='Arial, sans-serif',color='#152238',size=13),xaxis=dict(side='top',tickfont=dict(size=12)),yaxis=dict(autorange='reversed',tickfont=dict(size=13)))
    return fig


def overview(ranking,pillars):
    header('Tổng quan nghiên cứu','Bức tranh chuyển đổi số','So sánh năm công ty qua bốn trụ cột. Điểm R là trung bình có trọng số trên thang 100, được tính từ sắc thái thông tin công khai.')
    cols=st.columns(4)
    cols[0].metric('Công ty đánh giá',len(ranking))
    valid=ranking.dropna(subset=['R'])
    cols[1].metric('Điểm R cao nhất',f"{valid['R'].max():.2f}" if not valid.empty else 'Chưa đủ dữ liệu')
    cols[2].metric('Trụ cột',4)
    cols[3].metric('Trọng số', '40 · 20 · 30 · 10',help='Công nghệ · Khách hàng · Dữ liệu · Chiến lược (%)')
    st.markdown('<div class="note">Kết quả thử nghiệm từ dữ liệu công khai. Điểm 100 ở một trụ cột phản ánh tín hiệu quan sát tích cực, không khẳng định năng lực nội bộ hoàn hảo.</div>',unsafe_allow_html=True)
    st.subheader('Bản đồ điểm thành phần')
    selected=st.multiselect('Công ty hiển thị trên biểu đồ',ranking['company'].tolist(),default=ranking['company'].tolist())
    filtered=ranking[ranking['company'].isin(selected)]
    if filtered.empty:st.info('Chọn ít nhất một công ty để xem biểu đồ.')
    else:st.plotly_chart(heatmap(filtered),width='stretch',config={'displayModeBar':False})
    st.caption('Thang màu cố định 0–100. Di chuột để xem điểm chính xác; bảng bên dưới cung cấp cùng thông tin bằng số.')
    st.subheader('Bảng xếp hạng')
    display=ranking[['rank','company',*PILLARS,'R','level_label']].rename(columns={'rank':'Hạng','company':'Công ty','R':'Điểm R','level_label':'Phân mức'})
    config={p:st.column_config.NumberColumn(p,format='%.2f',min_value=0,max_value=100) for p in PILLARS+['Điểm R']}
    st.dataframe(display,hide_index=True,width='stretch',column_config=config)
    a,b=st.columns([1,1])
    a.download_button('Tải bảng điểm CSV',data=display.to_csv(index=False).encode('utf-8-sig'),file_name='DBI_bang_diem.csv',mime='text/csv')
    if (PUBLISHED/'heatmap.png').exists():b.download_button('Tải biểu đồ PNG',data=(PUBLISHED/'heatmap.png').read_bytes(),file_name='DBI_bieu_do_nhiet.png',mime='image/png')
    with st.expander('Độ phủ của các chỉ tiêu đang được dùng'):
        coverage=pillars.drop_duplicates('pillar')[['pillar','shared_indicators','defined_indicators','coverage_percent']].rename(columns={'pillar':'Trụ cột','shared_indicators':'Chỉ tiêu dùng','defined_indicators':'Chỉ tiêu định nghĩa','coverage_percent':'Độ phủ (%)'})
        st.dataframe(coverage,hide_index=True,width='stretch')
        st.caption('Độ phủ là phần chỉ tiêu có dữ liệu chung ở cả năm công ty, không phải tỷ lệ thu thập đầy đủ dữ liệu thực tế. Phần thiếu không tự nhận điểm 0 hoặc 50.')


def company_view(ranking,pillars):
    header('Phân tích chi tiết','Điểm số có thể truy vết','Xem đóng góp của từng trụ cột, nhóm nguồn và các đoạn văn đã được dùng để tính điểm.')
    company=st.selectbox('Chọn công ty',ranking['company'].tolist())
    row=ranking[ranking['company']==company].iloc[0]
    left,right=st.columns([1,2])
    left.metric('Điểm sẵn sàng R',f"{row['R']:.2f}" if pd.notna(row['R']) else 'Thiếu dữ liệu')
    left.write(f"**{row['level_label']}**" if pd.notna(row['level_label']) else 'Chưa phân mức')
    scores=[float(row[p])*w/100 for p,w in zip(PILLARS,WEIGHTS)]
    fig=go.Figure(go.Bar(x=scores,y=PILLARS,orientation='h',marker_color=['#2563eb','#2c8b94','#6474bd','#9aacc5'],text=[f'{v:.2f}' for v in scores],textposition='outside',hovertemplate='%{y}: %{x:.2f} điểm đóng góp<extra></extra>'))
    fig.update_layout(height=265,margin=dict(l=10,r=50,t=15,b=15),paper_bgcolor='white',plot_bgcolor='white',xaxis=dict(title='Điểm đóng góp vào R',range=[0,45]),yaxis=dict(autorange='reversed'),font=dict(color='#152238'))
    right.plotly_chart(fig,width='stretch',config={'displayModeBar':False})
    st.subheader('Chỉ tiêu và nhóm nguồn')
    cells=frame(PUBLISHED/'indicator_source_scores.csv')
    if cells.empty:cells=frame(OUTPUT/'results/diagnostics/indicator_source_scores.csv')
    if not cells.empty:
        cells=cells[cells['company']==company].copy();cells['Điểm /100']=cells['score_20']*5
        cells['Nguồn']=cells['source'].map(SOURCE_LABELS);cells['Chỉ tiêu']=cells['indicator'].map(INDICATORS).fillna(cells['indicator'])
        st.dataframe(cells[['pillar','Chỉ tiêu','Nguồn','Điểm /100','document_count','used_in_comparison']].rename(columns={'pillar':'Trụ cột','document_count':'Số tài liệu','used_in_comparison':'Được dùng chung'}),hide_index=True,width='stretch',column_config={'Điểm /100':st.column_config.NumberColumn(format='%.2f')})
        st.caption('Chỉ các ô có “Được dùng chung” mới tham gia so sánh. Báo cáo nhiều trang được gộp thành một tài liệu; số tài liệu không phải điểm cộng.')
    st.subheader('Đoạn văn đóng góp vào điểm')
    signals=frame(PUBLISHED/'unique_signals.csv')
    if signals.empty:signals=frame(OUTPUT/'results/diagnostics/unique_signals.csv')
    if signals.empty:st.info('Chưa có dữ liệu truy vết.');return
    col1,col2=st.columns(2)
    pillar=col1.selectbox('Lọc trụ cột',['Tất cả',*PILLARS])
    keyword=col2.text_input('Tìm trong nội dung',placeholder='Ví dụ: dữ liệu, bảo mật, giao diện…')
    subset=signals[signals['company']==company].copy()
    if pillar!='Tất cả':subset=subset[subset['pillar']==pillar]
    if keyword:subset=subset[subset['quote'].str.contains(keyword,case=False,regex=False,na=False)]
    st.caption(f'{len(subset):,} tín hiệu phù hợp. Hiển thị tối đa 200 dòng để đọc thuận tiện; file tải xuống chứa toàn bộ kết quả lọc.')
    subset['source']=subset['source'].map(SOURCE_LABELS)
    view=subset[['pillar','indicator','quote','tone','source','date','page','url','claim_status']].rename(columns={'pillar':'Trụ cột','indicator':'Mã chỉ tiêu','quote':'Đoạn trích','tone':'Tone [-1,1]','source':'Nhóm nguồn','date':'Ngày/kỳ','page':'Trang PDF','url':'Liên kết','claim_status':'Trạng thái tuyên bố'})
    st.dataframe(view.head(200),hide_index=True,width='stretch',column_config={'Liên kết':st.column_config.LinkColumn('Liên kết')})
    st.download_button('Tải các tín hiệu đã lọc',view.to_csv(index=False).encode('utf-8-sig'),file_name='DBI_tin_hieu.csv',mime='text/csv')


def methodology():
    header('Phương pháp & dữ liệu','Hiểu cách hình thành điểm','Một mô hình nghiên cứu cá nhân có thể chạy lại: từ văn bản công khai đến tín hiệu, điểm trụ cột và mức sẵn sàng.')
    tab1,tab2,tab3=st.tabs(['Dữ liệu đầu vào','Công thức & quy tắc','Giới hạn hệ thống'])
    with tab1:
        st.markdown('''### Hệ thống đọc những gì?

| Nhóm dữ liệu | Cách dùng |
|---|---|
| Review Google Play và App Store | Phản ánh trải nghiệm người dùng; chỉ tham gia trụ cột Khách hàng. Số sao dùng đối chiếu, không thay nhãn nội dung. |
| Báo cáo thường niên và tài chính công khai | Tìm các đoạn nói về công nghệ, dữ liệu, định hướng và nguồn lực số; giữ trang PDF để truy vết. Không yêu cầu dữ liệu nội bộ. |
| Báo chí và sự kiện từ hai bộ crawl | Dùng nội dung bài đạt kiểm tra. Hai bộ crawl được gộp thành một nhóm báo chí khi tính trọng số. |

VNG (VNZ) là đơn vị được xếp hạng; ZaloPay là sản phẩm thuộc phạm vi công ty này. Review ZaloPay không đại diện toàn bộ sản phẩm VNG.
''')
        run=read_json(PUBLISHED/'run.json')
        meta=read_json(PUBLISHED/'metadata.json') or read_json(OUTPUT/'results/diagnostics/metadata.json')
        audit=meta.get('audit',{})
        for key,label in [('reviews:documents','Review đã đọc'),('press:documents','Bài báo đã đọc'),('reports:documents','Trang báo cáo đã đọc')]:
            st.write(f"**{label}:** {audit.get(key,0):,}")
        st.caption('Số trang không phải số báo cáo độc lập. Số review/bài đọc cũng không đồng nghĩa số tín hiệu được giữ.')
        st.info('Phạm vi nguồn 2 hiện là bộ pilot đã lấy toàn văn, chưa khẳng định đã bao phủ toàn bộ tin trên thị trường.')
        st.markdown('### Bốn trụ cột')
        st.dataframe(pd.DataFrame({'Trụ cột':PILLARS,'Trọng số (%)':WEIGHTS,'Nội dung':['Hạ tầng, kết nối hệ thống, an toàn và xác thực','Trải nghiệm, hỗ trợ và tiếp cận dịch vụ số','Nền tảng, quản trị, phân tích dữ liệu và AI','Định hướng, quản trị chuyển đổi số và nguồn lực']}),hide_index=True,width='stretch')
    with tab2:
        st.markdown('### 1. Từ văn bản đến sắc thái')
        st.latex(r'Tone=\frac{P-N}{P+N}\in[-1,1]')
        st.write('P và N là số lần khớp cụm từ tích cực và tiêu cực sau xử lý phủ định. Khớp cụm dài nhất để tránh đếm lặp từ nằm trong cụm. Cảnh báo/phòng chống không tự được coi là sự cố đã xảy ra.')
        st.write('Không có tín hiệu cảm xúc thì đoạn không tham gia tính điểm; không tự nhận điểm trung lập. Một đoạn có cả khen/chê có thể có tone gần 0.')
        st.markdown('### 2. Tổng hợp công bằng')
        st.markdown('''1. Mỗi đoạn chỉ vào **một chỉ tiêu và một trụ cột**; ưu tiên Dữ liệu → Chiến lược → Công nghệ → Khách hàng trong mô hình bốn trụ cột.
2. Loại đoạn trùng chính xác; lọc trùng gần ở tin/báo cáo theo độ giống nhau của cụm từ, giữ riêng thông tin có số liệu mới. Chưa bảo đảm gom hoàn toàn mọi bài cùng sự kiện.
3. Trung bình tone trong mỗi tài liệu, rồi trung bình các tài liệu trong một ô chỉ tiêu/nhóm nguồn. Gộp các trang cùng báo cáo thành một tài liệu.
4. Chỉ dùng các ô có dữ liệu chung cho cả năm công ty. Chia đều nhóm nguồn trong chỉ tiêu và các chỉ tiêu dùng được trong trụ cột. Không đổi trọng số riêng cho công ty có ít bài.
5. Giải thưởng, khuyến mại, câu lẫn kế hoạch/kết quả và đoạn có tham chiếu trước 2025 bị loại. Kế hoạch còn lại chỉ phản ánh giọng điệu định hướng, không chứng minh thành tựu.
''')
        st.latex(r'S_{\mathrm{nguồn}}=50(1+\overline{Tone}),\qquad S_{\mathrm{trụ\ cột}}\in[0,100]')
        st.markdown('### 3. Điểm sẵn sàng và phân mức')
        st.latex(r'R=\frac{40S_{CN}+20S_{KH}+30S_{DL}+10S_{CL}}{40+20+30+10}')
        st.write('Không chia thêm cho 4. Phân mức bằng điểm chưa làm tròn; nếu thiếu cả trụ cột thì không tự tính tổng bằng cách gán 0 hay đổi tỷ trọng.')
        st.table(pd.DataFrame({'Mức':[1,2,3,4,5],'Tên':['Cơ bản','Đang phát triển','Phát triển','Nâng cao','Dẫn đầu'],'Ngưỡng R':['0 ≤ R < 25','25 ≤ R < 50','50 ≤ R < 75','75 ≤ R < 100','R = 100 chính xác']}))
    with tab3:
        st.markdown('''### Cần đọc điểm số như thế nào?

- **Đây là chỉ số từ sắc thái công khai**, chưa phải xác nhận năng lực hay mức trưởng thành số thực tế. Các mức là quy ước của dự án.
- Báo cáo tự công bố và tin quảng bá thường tích cực, khiến Dữ liệu hoặc Chiến lược dễ chạm trần. Điểm 100 không đồng nghĩa mọi khía cạnh đều tốt.
- Review là phản hồi tự chọn, có chênh lệch nền tảng, thời gian và lượng thu thập. Không đại diện ngẫu nhiên cho toàn bộ khách hàng.
- Chỉ dùng dữ liệu chung giúp cùng trọng số nhưng có thể bỏ nhiều chỉ tiêu. Độ phủ thấp làm kết quả kém toàn diện.
- Từ điển và regex có thể bỏ sót tiếng lóng, mỉa mai, phủ định phức tạp, câu đa chủ thể. OCR có thể sai dấu và mất cấu trúc bảng.
- Dedupe chưa nhận diện hoàn toàn cùng sự kiện được diễn đạt khác nhau. Ngày đăng bài không nhất thiết là ngày xảy ra sự kiện.
- Chưa có đánh giá độc lập về độ chính xác và khoảng tin cậy thứ hạng. Chênh lệch nhỏ giữa hai công ty chưa chứng minh khác biệt đáng kể.
- VNG là tập đoàn công nghệ, bốn đơn vị còn lại là ngân hàng. Cần nêu rõ phạm vi mẫu khi trình bày kết luận.

### Hướng cải thiện

Tự gán nhãn một tập kiểm tra riêng; tăng độ phủ các nguồn toàn văn; gom sự kiện; kiểm tra PDF; đánh giá độ nhạy theo nguồn và trọng số. Không cần dữ liệu mật hoặc thuê đơn vị kiểm định để phát triển bản nghiên cứu cá nhân.
''')


def pipeline_page():
    header('Vận hành nghiên cứu','Pipeline & xuất kết quả','Chạy lại các bước trên dữ liệu đang có. Bản tính cuối cùng thành công được giữ lại để xem trong lúc hệ thống xử lý.')
    st.markdown('**Luồng xử lý:** dữ liệu công khai → làm sạch toàn văn → sentiment → ứng viên bằng chứng → gán bốn trụ cột → loại trùng → điểm R → biểu đồ nhiệt.')
    if st.button('Chạy lại trên dữ liệu hiện có',type='primary',disabled=(OUTPUT/'.pipeline.lock').exists()):
        if start_pipeline():st.success('Đã khởi chạy. Nhấn “Cập nhật trạng thái” để theo dõi.')
        else:st.info('Một pipeline đang chạy.')
    if st.button('Cập nhật trạng thái'):st.rerun()
    state=read_json(OUTPUT/'pipeline_status.json')
    labels={'running':'Đang chạy','completed':'Hoàn thành','failed':'Có lỗi'}
    st.write('**Trạng thái:** '+labels.get(state.get('status'),'Chưa chạy'))
    if state.get('error'):st.error(state['error'])
    for item in state.get('stages',[]):
        st.markdown(f"**{item['name']}** · {labels.get(item['status'],item['status'])}"+(f" · {item['elapsed_seconds']} giây" if 'elapsed_seconds' in item else ''))
    st.markdown('### Thu thập mới khi cần')
    st.write('Lệnh mặc định không crawl lại. Các lệnh dưới chạy từ thư mục dự án bằng interpreter đã cấu hình; thu thập mới cần mạng và có thể mất nhiều thời gian.')
    st.code('python run_pipeline.py\npython run_pipeline.py --enrich-source2 --per-company 50\npython run_pipeline.py --refresh --per-company 50\npython -m streamlit run app.py',language='bash')
    st.caption('Để xử lý toàn bộ danh sách nguồn 2, tăng --per-company, ví dụ 100000. Không bảo đảm mọi bài đều tải được; lỗi từng bài được lưu riêng.')
    for name,label in [('REPORT.md','Tải báo cáo phương pháp'),('method.json','Tải cấu hình phương pháp'),('heatmap.svg','Tải biểu đồ SVG')]:
        path=PUBLISHED/name
        if path.exists():st.download_button(label,path.read_bytes(),file_name=name,key='download_'+name)


def main():
    with st.sidebar:
        st.markdown('<div class="brand"><span class="brand-mark">DBI</span><div><div class="brand-name">DBI Research</div><div class="brand-sub">Chuyển đổi số · Dữ liệu công khai</div></div></div>',unsafe_allow_html=True)
        page=st.radio('Không gian nghiên cứu',['Tổng quan','Chi tiết công ty','Phương pháp & dữ liệu','Pipeline & tải xuống'],label_visibility='collapsed')
        st.divider()
        st.caption('MÔ HÌNH BỐN TRỤ CỘT')
        for p,w in zip(PILLARS,WEIGHTS):st.markdown(f'**{p}** · {w}%')
        st.divider()
        run=read_json(PUBLISHED/'run.json')
        st.caption('Lần tính thành công gần nhất')
        stamp=run.get('finished_at_utc','')
        st.write(stamp[:16].replace('T',' ')+' UTC' if stamp else 'Chưa có')
        st.caption('Nghiên cứu cá nhân · Kết quả thử nghiệm')
    if page=='Pipeline & tải xuống':pipeline_page();return
    if page=='Phương pháp & dữ liệu':methodology();return
    ranking=frame(PUBLISHED/'ranking.csv');pillars=frame(PUBLISHED/'pillar_scores.csv')
    if ranking.empty or pillars.empty:
        header('Chưa có kết quả','Khởi tạo nghiên cứu','Chạy pipeline một lần để tính điểm và tạo biểu đồ từ dữ liệu hiện có.')
        if st.button('Tính điểm lần đầu',type='primary'):
            start_pipeline();st.info('Đã khởi chạy. Mở Pipeline & tải xuống để xem tiến độ.')
        return
    if page=='Tổng quan':overview(ranking,pillars)
    else:company_view(ranking,pillars)
    st.markdown('<div class="footer">DBI Research · Điểm số phản ánh thông tin công khai trong phạm vi dữ liệu thu thập. Không phải xếp hạng chính thức hoặc tư vấn đầu tư.</div>',unsafe_allow_html=True)


if __name__=='__main__':main()
