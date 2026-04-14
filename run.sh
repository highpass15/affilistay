#!/bin/bash

# 데이터베이스 초기화
python database.py

# 백엔드 서버(FastAPI) 실행 (백그라운드)
uvicorn checkout_server:app --host 0.0.0.0 --port 8000 &

# 어드민 서버(Streamlit) 실행
# Render나 Vercel에서는 단일 포트 노출이 기본이므로, 포트 설정을 유의해야 합니다.
python -m streamlit run admin_dashboard_ui.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
