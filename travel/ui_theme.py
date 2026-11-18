"""필수 입력과 합계를 중심으로 한 간결한 화면 스타일."""
import streamlit as st

CSS = '''<style>
.stApp {background:#f7f8fa;color:#202c3b;}
.stApp,input,textarea,button {font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;}
.block-container {max-width:760px;padding:4.5rem 1.5rem 2rem;}
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
.batch-row {display:flex;justify-content:space-between;gap:1rem;align-items:center;border-bottom:1px solid #edf0f4;padding:.6rem 0;font-size:.85rem;}
.batch-row small {display:block;font-size:.72rem;color:#8791a0;margin-top:.2rem;}
.batch-row strong {white-space:nowrap;font-size:.9rem;}
@media(max-width:600px) {
 .block-container {padding:4.25rem 1rem 1.5rem;}
 .st-key-inputs,.st-key-result {padding:1rem!important;}
 .result-amount {font-size:2.15rem;}
 .result-breakdown strong {font-size:.84rem;}
}
@media(max-width:370px) {
 .result-breakdown {grid-template-columns:repeat(2,minmax(0,1fr));gap:.8rem;}
}
</style>'''


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)
