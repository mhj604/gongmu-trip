#!/bin/zsh
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo '먼저 README의 Python 환경 설치 명령을 실행해 주세요.'
  exit 1
fi
exec .venv/bin/python -m streamlit run app.py
