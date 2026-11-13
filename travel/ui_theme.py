"""바른여비 화면의 색상, 여백과 공통 표시 구성."""
from html import escape
from datetime import datetime
import streamlit as st
from .models import money
from .report import status_label

PAGE_INFO={
    '새 출장 등록':('출장 정보','출장의 기본정보를 입력해 주세요.','출장 정보'),
    '국내 출장 계산':('국내 출장','일정과 지출 내역을 한곳에서 관리하세요.','국내 출장'),
    '국외 출장 계산':('국외 출장','방문 국가와 통화에 맞춰 여비를 계산하세요.','국외 출장'),
    '특수 여비 계산':('특수 여비','준비금·이전비·가족여비를 추가하세요.','특수 여비'),
    '계산 결과 및 정산서':('출장비 정산서','계산 내역을 확인하고 정산서를 내려받으세요.','정산서'),
    '저장된 출장 내역':('출장 보관함','저장한 출장을 불러오거나 복사할 수 있어요.','보관함'),
    '법령 및 지급 기준 안내':('지급 기준','적용 법령과 국가·도시별 지급 기준을 살펴보세요.','지급 기준'),
    '프로그램 설정':('설정','계산 기준과 개인 기록을 관리하세요.','설정'),
}

CSS='''<style>
:root { --ink:#1c2e44; --muted:#788597; --accent:#245ec7; --line:#e5eaf0; }
.stApp {background:#f6f8fb;color:var(--ink);}
.stApp, input, textarea, button {font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;}
.block-container {max-width:1260px;padding:2rem 2.5rem 4rem;}
[data-testid="stHeader"] {background:rgba(246,248,251,.96);}
[data-testid="stAppDeployButton"] {display:none;}
h1,h2,h3 {color:var(--ink);letter-spacing:-.045em;font-weight:700;}
h1 {font-size:2rem!important;padding:.15rem 0 .35rem!important;line-height:1.3!important;}
h3 {font-size:1.1rem!important;}
[data-testid="stCaptionContainer"] {color:var(--muted);font-size:.8rem;line-height:1.65;}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid var(--line);}
[data-testid="stSidebar"]>div:first-child {padding-top:1.2rem;}
[data-testid="stSidebarUserContent"] {padding:1.25rem 1.15rem;}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {gap:.25rem;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    border:1px solid transparent;border-radius:9px;padding:.65rem .85rem!important;
    margin:0!important;width:100%;min-height:43px;color:#647184;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadio"] label:has([aria-checked="true"]) {
    background:#edf3ff;color:#245ec7;border-color:#e5edff;font-weight:650;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background:#f5f7fa;}
[data-testid="stSidebar"] [data-testid="stRadio"] label>div:first-child {display:none;}
[data-testid="stSidebar"] [data-testid="stRadio"] label p {font-size:.88rem;}
[data-testid="stSidebar"] [data-testid="stButton"] button {font-size:.86rem;}
.brand {display:flex;align-items:center;gap:11px;margin:0 0 1.8rem .15rem;}
.brand-mark {display:grid;place-items:center;width:38px;height:38px;border-radius:12px;background:#1c2e44;}
.brand-name {font-size:1.28rem;font-weight:750;letter-spacing:-.05em;color:#1c2e44;line-height:1.3;}
.brand-note {font-size:.68rem;color:#8a96a5;margin-top:3px;letter-spacing:.01em;}
.nav-label {font-size:.68rem;color:#98a3b1;letter-spacing:.07em;margin:1.2rem .8rem .45rem;}
.sidebar-note {font-size:.7rem;line-height:1.8;color:#929cab;padding:.5rem .4rem;}
.page-crumb {font-size:.72rem;color:#8a95a5;letter-spacing:.01em;margin:.2rem 0 .65rem;}
.page-description {font-size:.88rem;color:#7a8798;margin:0 0 1.6rem;line-height:1.7;}
.stepper {display:flex;align-items:center;gap:1rem;margin:.2rem 0 1.6rem;}
.step {display:flex;align-items:center;gap:.5rem;color:#9aa5b3;font-size:.77rem;white-space:nowrap;}
.step-num {display:grid;place-items:center;width:24px;height:24px;border:1px solid #dce3ec;border-radius:50%;font-size:.65rem;background:#fff;}
.step.current {color:#245ec7;font-weight:650;}
.step.current .step-num {background:#245ec7;color:#fff;border-color:#245ec7;}
.step.done .step-num {color:#245ec7;border-color:#d4e2ff;background:#edf3ff;}
.step-line {width:42px;height:1px;background:#dfe5ed;}
.st-key-trip_overview,.st-key-traveler_card,.st-key-schedule_card,.st-key-destination_card,
.st-key-summary_panel,.st-key-result_panel,.st-key-result_details,.st-key-settings_panel,
.st-key-rules_panel,.st-key-saved_panel,.st-key-special_panel {
    background:#fff;border:1px solid var(--line)!important;border-radius:15px!important;
    padding:1.35rem 1.45rem!important;box-shadow:0 2px 7px rgba(26,48,78,.018);
}
.form-heading {display:flex;align-items:center;gap:9px;margin:.05rem 0 .85rem;font-size:.94rem;font-weight:700;letter-spacing:-.035em;}
.form-index {font-size:.62rem;letter-spacing:.02em;color:#7c91ac;background:#f0f4f9;border-radius:6px;padding:4px 6px;}
[data-testid="stWidgetLabel"] p {font-size:.79rem!important;color:#617086;font-weight:550;}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea {font-size:.88rem;color:#25364d;}
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"] {
    background:#f9fafc!important;border:1px solid #e7ebf1!important;border-radius:8px!important;
}
[data-testid="stTextInputRootElement"]:focus-within,[data-testid="stTextAreaRootElement"]:focus-within {
    border-color:#7ba2e9!important;box-shadow:0 0 0 3px #edf3ff!important;
}
[data-testid="stTextInput"] input::placeholder,[data-testid="stTextArea"] textarea::placeholder {color:#b1bac7;}
[data-testid="stSelectbox"] [role="combobox"], [data-testid="stDateInput"] [role="group"],
[data-testid="stTimeInput"] [role="group"] {border-radius:8px;background:#f9fafc;}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button,[data-testid="stPopover"] button {
    border-radius:9px;min-height:39px;font-size:.83rem;font-weight:550;border-color:#e1e7ee;
    box-shadow:none;transition:background .15s,border-color .15s;
}
[data-testid="stButton"] button[kind="primary"], [data-testid="stDownloadButton"] button[kind="primary"] {
    background:#245ec7;border-color:#245ec7;color:#fff;
}
[data-testid="stButton"] button[kind="primary"]:hover {background:#1b4fae;border-color:#1b4fae;}
[data-testid="stExpander"] {border-color:#e6ebf2!important;border-radius:10px!important;box-shadow:none;}
[data-testid="stExpander"] details summary {font-size:.8rem;color:#65748a;}
[data-testid="stExpander"] details summary p {font-size:.8rem;}
[data-testid="stTabs"] [role="tablist"] {gap:1.5rem;border-bottom:1px solid var(--line);padding:0 .15rem;}
[data-testid="stTabs"] [role="tab"] {font-size:.84rem;color:#8290a1;padding:.7rem .1rem;}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {color:#245ec7;font-weight:650;}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {background:#245ec7;height:2px;}
[data-testid="stDataFrame"] {border:1px solid #e7ecf2;border-radius:10px;overflow:hidden;}
[data-testid="stAlert"] {border-radius:9px;font-size:.8rem;}
.duration {display:flex;gap:8px;margin:.2rem 0 .35rem;}
.duration span,.type-tag {font-size:.71rem;color:#637891;background:#f0f4f9;padding:5px 9px;border-radius:6px;}
.summary-top {display:flex;align-items:center;justify-content:space-between;margin:0 0 1.7rem;}
.summary-title {font-size:.84rem;font-weight:650;}
.summary-label {color:#8390a1;font-size:.73rem;margin-bottom:.5rem;}
.summary-amount {font-size:2rem;line-height:1.25;font-weight:750;color:#1c2e44;letter-spacing:-.055em;font-variant-numeric:tabular-nums;margin-bottom:.7rem;overflow-wrap:anywhere;}
.summary-hint {font-size:.72rem;line-height:1.75;color:#8c98a7;}
.summary-divider {border-top:1px solid #edf0f5;margin:1.25rem 0 1rem;}
.summary-row {display:flex;justify-content:space-between;gap:12px;font-size:.76rem;color:#8a96a6;margin:.7rem 0;}
.summary-row strong {color:#43556f;font-weight:550;overflow-wrap:anywhere;text-align:right;}
.summary-state {font-size:.7rem;color:#718199;background:#f6f8fb;border-radius:7px;padding:.7rem .8rem;margin-top:1.1rem;line-height:1.65;}
.summary-state.ready {background:#edf8f5;color:#3e7a66;}
.result-kicker {font-size:.75rem;color:#8995a6;margin:.25rem 0 .55rem;}
.result-amount {font-size:2.8rem;font-weight:750;line-height:1.25;letter-spacing:-.055em;color:#1b3657;font-variant-numeric:tabular-nums;}
.result-stats {display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #e9eef4;margin:1.5rem 0 .2rem;padding-top:1.1rem;gap:1rem;}
.result-stats small {display:block;font-size:.7rem;color:#929dae;margin-bottom:.4rem;}
.result-stats strong {font-size:1rem;font-weight:650;color:#4b5e77;font-variant-numeric:tabular-nums;}
.result-note {font-size:.74rem;color:#8896a7;margin-top:.7rem;line-height:1.7;}
.empty-state {padding:2rem 1rem;text-align:center;color:#9aa6b5;}
.empty-icon {color:#a5b5c8;display:block;margin-bottom:.8rem;font-size:1.8rem;}
.empty-state strong {display:block;color:#61748b;font-size:.94rem;font-weight:600;margin-bottom:.45rem;}
.empty-state p {font-size:.8rem;line-height:1.8;}
.footer-note {font-size:.69rem;color:#a0aab7;text-align:center;margin:1rem 0 .3rem;}
@media(min-width:1100px) {.st-key-summary_column {position:sticky;top:5rem;}}
@media(max-width:900px) {
    .block-container {padding:1.3rem 1.25rem 2.5rem;}
    .st-key-workspace_columns [data-testid="stHorizontalBlock"]:has(.st-key-summary_column) {flex-wrap:wrap;}
    .st-key-workspace_columns [data-testid="stHorizontalBlock"]:has(.st-key-summary_column)>[data-testid="stColumn"] {width:100%!important;flex:1 1 100%!important;min-width:100%!important;}
}
@media(max-width:600px) {
    h1 {font-size:1.65rem!important;}
    .block-container {padding:1.2rem 1rem 2rem;}
    .st-key-trip_overview,.st-key-traveler_card,.st-key-schedule_card,.st-key-destination_card,
    .st-key-summary_panel,.st-key-result_panel,.st-key-result_details,.st-key-special_panel {padding:1rem!important;border-radius:12px!important;}
    .stepper {gap:.5rem;margin-bottom:1.1rem;}
    .step {font-size:.7rem;gap:.35rem;}
    .step-line {width:18px;}
    .page-description {font-size:.8rem;margin-bottom:1rem;}
    .summary-amount {font-size:1.9rem;}
    .result-amount {font-size:2.2rem;}
    .result-stats {gap:.5rem;}
    .result-stats strong {font-size:.87rem;}
    [data-testid="stTabs"] [role="tablist"] {gap:1rem;}
}
@media(prefers-reduced-motion:reduce) {*{transition:none!important;}}
</style>'''

def apply_theme():st.markdown(CSS,unsafe_allow_html=True)

def brand():
    st.markdown('''<div class="brand"><span class="brand-mark"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="7" width="18" height="13" rx="3" stroke="white" stroke-width="1.5"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12c5 3 13 3 18 0M12 11v4" stroke="white" stroke-width="1.5" stroke-linecap="round"/></svg></span><div><div class="brand-name">바른여비</div><div class="brand-note">나의 공무 출장 정산</div></div></div>''',unsafe_allow_html=True)

def page_header(page):
    title,description,_=PAGE_INFO[page]
    st.markdown('<div class="page-crumb">바른여비&nbsp;&nbsp; / &nbsp;&nbsp;'+escape(title)+'</div>',unsafe_allow_html=True)
    st.title(title)
    st.markdown('<div class="page-description">'+escape(description)+'</div>',unsafe_allow_html=True)
    if page in list(PAGE_INFO)[:5]:
        active=0 if page=='새 출장 등록' else 2 if page=='계산 결과 및 정산서' else 1
        parts=[]
        for i,name in enumerate(['출장 정보','비용 입력','정산서']):
            state='current' if i==active else 'done' if i<active else ''
            if i:parts.append('<span class="step-line"></span>')
            parts.append(f'<span class="step {state}"><span class="step-num">{i+1:02}</span>{name}</span>')
        st.markdown('<div class="stepper" aria-label="출장 정산 단계">'+''.join(parts)+'</div>',unsafe_allow_html=True)

def section_heading(number,title):
    st.markdown(f'<div class="form-heading"><span class="form-index">{number:02}</span>{escape(title)}</div>',unsafe_allow_html=True)

def empty_state(title,description):
    st.markdown(f'<div class="empty-state"><span class="empty-icon">▤</span><strong>{escape(title)}</strong><p>{escape(description)}</p></div>',unsafe_allow_html=True)

def summary_html(result):
    trip=result.trip
    meta=trip['meta']
    try:
        start=datetime.fromisoformat(meta['시작일시']);end=datetime.fromisoformat(meta['종료일시'])
        days=max(0,(end.date()-start.date()).days+1)
    except (ValueError,KeyError):days=0
    started=bool(meta.get('출장명') and meta.get('성명'))
    amount=money(result.claim) if started else '—'
    state=f'확인할 항목 {len(result.issues)}건 · 정산서에서 자세히 보기' if started and result.issues else '필수정보를 입력하면 계산을 시작해요.' if not started else '입력한 내역으로 계산했어요.'
    st.markdown(f'''<div class="summary-top"><span class="summary-title">이번 출장</span><span class="type-tag">{escape(trip['kind'])}</span></div>
<div class="summary-label">{escape(status_label(result))}</div><div class="summary-amount">{escape(amount)}</div>
<div class="summary-hint">{escape(meta.get('출장명') or '새로운 출장을 준비하고 있어요.')}</div>
<div class="summary-divider"></div>
<div class="summary-row"><span>출장자</span><strong>{escape(meta.get('성명') or '미입력')}</strong></div>
<div class="summary-row"><span>일정</span><strong>{days}일 · 숙박 {len(trip['lodgings'])}박 입력</strong></div>
<div class="summary-row"><span>지급등급</span><strong>{escape(meta.get('지급등급') or '미입력')}</strong></div>
<div class="summary-row"><span>기지급액</span><strong>{escape(money(result.advance))}</strong></div>
<div class="summary-state {'ready' if started and not result.issues else ''}">{escape(state)}</div>''',unsafe_allow_html=True)

def result_overview(result):
    st.markdown(f'''<div class="result-kicker">{escape(status_label(result))}</div>
<div class="result-amount">{escape(money(result.claim))}</div>
<div class="result-stats"><div><small>확정 인정액</small><strong>{escape(money(result.recognized))}</strong></div>
<div><small>기지급액</small><strong>{escape(money(result.advance))}</strong></div>
<div><small>미확정 산정액</small><strong>{escape(money(result.pending))}</strong></div></div>''',unsafe_allow_html=True)
    if result.issues:st.markdown(f'<div class="result-note">미확정 항목은 청구액에서 제외했어요. 확인 사항 {len(result.issues)}건을 살펴보세요.</div>',unsafe_allow_html=True)
    if result.refund:st.caption('반납예정액 '+money(result.refund))
