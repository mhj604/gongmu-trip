"""쉼표 표시와 숫자 원문을 분리하는 금액 입력 위젯."""
from pathlib import Path
import streamlit as st
from .models import dec

_ROOT = Path(__file__).parent/'components'
_money = st.components.v2.component('gongmu_money',
    html='<label></label><input type="text" inputmode="decimal" autocomplete="off" /><small class="help" hidden></small><small class="error" hidden>0 이상의 숫자를 입력하세요.</small>',
    css='''
    :host {display:block;font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;}
    label {display:block;font-size:12.8px;color:#5b6675;margin:0 0 8px;line-height:1.4;}
    input {box-sizing:border-box;width:100%;height:40px;border:1px solid #d7dce3;border-radius:7px;background:#fff;color:#202c3b;padding:8px 12px;font:inherit;font-size:14px;outline:none;font-variant-numeric:tabular-nums;}
    input:focus {border-color:#245ec7;box-shadow:0 0 0 1px #245ec7;}
    input[aria-invalid="true"] {border-color:#c53636;}
    small {display:block;margin-top:5px;font-size:11px;line-height:1.5;color:#778191;}
    .error {color:#c53636;} [hidden] {display:none;}
    ''', js=(_ROOT/'money_input.js').read_text())


def plain_amount(value):
    if value in ('',None):
        return ''
    return format(dec(value).normalize(),'f')


def amount_input(label, value='', *, key, help=None):
    state = st.session_state.get(key,{})
    raw = state.get('value',plain_amount(value))
    result = _money(key=key,data={'label':label,'value':raw,'help':help or ''},
                    default={'value':raw},on_value_change=lambda: None)
    raw = result.value
    if raw == '':
        return None
    return dec(raw)
