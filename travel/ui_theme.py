"""필수 입력과 합계를 중심으로 한 간결한 화면 스타일."""
import streamlit as st

CSS = '''<style>
.stApp {background:#f7f8fa;color:#202c3b;}
.stApp,input,textarea,button {font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;}
.block-container {max-width:760px;padding:4.5rem 1.5rem 2rem;}
[data-testid="stMain"] {scroll-padding-bottom:calc(6rem + env(safe-area-inset-bottom,0px));}
[data-testid="stHeader"] {background:rgba(247,248,250,.96);}
[data-testid="stAppDeployButton"] {display:none;}
h1 {font-size:1.65rem!important;font-weight:700!important;line-height:1.4!important;letter-spacing:-.045em;padding:.1rem 0!important;}
[data-testid="stCaptionContainer"] {color:#778191;line-height:1.55;}
.st-key-inputs,.st-key-result {background:#fff;border:1px solid #e5e8ed!important;border-radius:12px!important;padding:1.1rem 1.25rem!important;}
.st-key-inputs [data-testid="stVerticalBlock"],.st-key-result [data-testid="stVerticalBlock"] {gap:.65rem;}
[data-testid="stWidgetLabel"] p {font-size:.8rem;color:#5b6675;}
[data-testid="stTextInputRootElement"],[data-testid="stNumberInputContainer"],
[data-testid="stSelectbox"] [role="combobox"] {border-radius:7px;background:#fff;}
[data-testid="stNumberInputContainer"] button {display:none;}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button,[data-testid="stPopover"] button {border-radius:7px;font-size:.82rem;min-height:36px;}
[data-testid="stExpander"] {border:0;border-top:1px solid #e5e8ed;border-radius:0;background:transparent;}
[data-testid="stExpander"] summary p {font-size:.84rem;color:#687587;}
[data-testid="stDataFrame"] {border:1px solid #e5e8ed;border-radius:7px;overflow:hidden;}
[data-testid="stTabs"] [role="tablist"] {gap:1.25rem;}
.result-heading {display:flex;justify-content:space-between;align-items:center;font-size:.83rem;color:#657184;}
.result-heading span:last-child {font-size:.76rem;color:#929aa6;}
.result-amount {font-size:2.5rem;font-weight:750;letter-spacing:-.055em;color:#245ec7;line-height:1.4;font-variant-numeric:tabular-nums;}
.result-breakdown {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.5rem;border-top:1px solid #edf0f4;padding-top:.85rem;margin-top:.35rem;}
.result-breakdown span {display:block;color:#8791a0;font-size:.74rem;margin-bottom:.25rem;}
.result-breakdown strong {display:block;font-size:.95rem;font-weight:600;letter-spacing:-.025em;font-variant-numeric:tabular-nums;}
[class*="st-key-trip-card-"] {border:1px solid #e5eaf1;border-radius:12px;padding:18px 20px;background:#fff;min-width:0;}
.trip-card-heading {display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:12px;align-items:center;}
[class*="st-key-trip-actions-"] [data-testid="stHorizontalBlock"] {flex-wrap:nowrap;gap:.2rem;}
[class*="st-key-trip-actions-"] [data-testid="stColumn"] {min-width:0!important;}
[class*="st-key-trip-actions-"] button {white-space:nowrap;font-size:.78rem!important;padding:.25rem .3rem!important;}
[class*="st-key-delete-trip-"] button {color:#b64b55;}
.st-key-inputs {scroll-margin-top:5rem;}
.trip-number {display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:#eef3fc;color:#3563af;font-size:.8rem;font-weight:700;}
.trip-identity {min-width:0;}
.trip-identity strong {display:block;font-size:.93rem;line-height:1.5;overflow-wrap:anywhere;}
.trip-identity span,.trip-total span {display:block;color:#8791a0;font-size:.72rem;line-height:1.6;}
.trip-total {text-align:right;}
.trip-total strong {display:block;color:#245ec7;font-size:1.06rem;font-variant-numeric:tabular-nums;white-space:nowrap;}
[class*="st-key-trip-card-"] .result-breakdown {margin-top:8px;padding-top:14px;gap:12px;}
[class*="st-key-trip-card-"] .result-breakdown strong {font-size:1rem;white-space:nowrap;}
@media(max-width:600px) {
 .block-container {padding:4.25rem 1rem 1.5rem;}
 .st-key-inputs,.st-key-result {padding:1rem!important;}
 .result-amount {font-size:2.15rem;}
 .result-breakdown strong {font-size:.84rem;}
 [class*="st-key-trip-card-"] {padding:16px;}
 .trip-card-heading {grid-template-columns:26px minmax(0,1fr);gap:10px;}
 .trip-number {width:26px;height:26px;}
 .trip-total {grid-column:2;text-align:left;}
 .trip-total span {display:none;}
 [class*="st-key-trip-card-"] .result-breakdown {grid-template-columns:repeat(2,minmax(0,1fr));row-gap:14px;}
}
@media(max-width:370px) {
 .result-breakdown {grid-template-columns:repeat(2,minmax(0,1fr));gap:.8rem;}
}
.block-container {padding-bottom:calc(6rem + env(safe-area-inset-bottom,0px));}
</style>'''


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


_scroll = st.components.v2.component('gongmu_scroll_inputs',html='',css=':host {display:none;}',js='''
export default function({parentElement}) {
  const doc = parentElement.ownerDocument;
  const view = doc.defaultView;
  let frame, attempts = 0;
  const move = () => {
    const target = doc.querySelector('.st-key-inputs');
    if (!target) {
      if (++attempts < 60) frame = view.requestAnimationFrame(move);
      return;
    }
    target.scrollIntoView({block:'start', behavior:view.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    target.querySelector('input:not([disabled])')?.focus({preventScroll:true});
  };
  frame = view.requestAnimationFrame(move);
  return () => view.cancelAnimationFrame(frame);
}
''')


def scroll_to_inputs(request):
    _scroll(key='edit-scroll-'+request)
