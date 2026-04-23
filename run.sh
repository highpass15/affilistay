#!/bin/bash
# 이 파일은 기본 실행용이지만 Render에서는 render.yaml의 dockerCommand가 우선권을 갖습니다.
python database.py
if [ "$SERVICE_TYPE" == "admin" ]; then
    streamlit run admin_dashboard_ui.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
else
    uvicorn checkout_server:app --host 0.0.0.0 --port $PORT
fi
