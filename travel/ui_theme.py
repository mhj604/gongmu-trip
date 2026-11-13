"""계산기에 필요한 최소한의 화면 스타일."""
import streamlit as st

CSS = '''<style>
.stApp {background:#f6f8fb;color:#1c2e44;}
.stApp,input,textarea,button {font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;}
.block-container {max-width:860px;padding:2rem 1.5rem 3rem;}
[data-testid="stHeader"] {background:rgba(246,248,251,.95);}
[data-testid="stAppDeployButton"] {display:none;}
h1 {font-size:1.85rem!important;letter-spacing:-.045em;padding:.1rem 0!important;}
[data-testid="stCaptionContainer"] {color:#7b899b;line-height:1.65;}
.st-key-inputs,.st-key-result {background:white;border:1px solid #e5eaf0!important;border-radius:16px!important;padding:1.25rem!important;}
.st-key-result {background:#fff;}
[data-testid="stWidgetLabel"] p {font-size:.82rem;color:#53657e;}
[data-testid="stTextInputRootElement"],[data-testid="stNumberInputContainer"],
[data-testid="stSelectbox"] [role="combobox"] {border-radius:9px;background:#f8fafc;}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button,[data-testid="stPopover"] button {border-radius:9px;font-size:.84rem;min-height:40px;}
[data-testid="stExpander"] {border:1px solid #e5eaf0;border-radius:10px;}
[data-testid="stDataFrame"] {border:1px solid #e5eaf0;border-radius:9px;overflow:hidden;}
[data-testid="stTabs"] [role="tablist"] {gap:1.25rem;}
[data-testid="stMetricLabel"] p {font-size:.75rem;color:#7b899b;}
[data-testid="stMetricValue"] {font-size:1.05rem;font-weight:600;}
.result-kicker {font-size:.84rem;color:#6c7d94;margin:.1rem 0 .3rem;}
.result-amount {font-size:2.6rem;font-weight:750;letter-spacing:-.055em;color:#245ec7;line-height:1.3;font-variant-numeric:tabular-nums;}
@media(max-width:600px) {
 .block-container {padding:1.2rem 1rem 2rem;}
 .st-key-inputs,.st-key-result {padding:1rem!important;}
 .result-amount {font-size:2.1rem;}
 [data-testid="stMetricValue"] {font-size:.95rem;}
}
</style>'''


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)
