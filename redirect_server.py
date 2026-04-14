from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
import uvicorn
from database import get_db_connection

app = FastAPI(title="QR Redirect Server")

@app.get("/")
def read_root():
    return {"status": "MVP Redirect Server is running"}

@app.get("/qr/{short_code}")
def redirect_to_product(short_code: str, request: Request):
    """
    QR 코드 링크( /qr/xxx )로 접속 시 호출됩니다.
    클릭 통계를 남기고 원본 업체의 URL로 우회(리다이렉트)시킵니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 프로모션 코드가 있는지 확인
    cursor.execute('SELECT target_url FROM promotions WHERE qr_short_code = ?', (short_code,))
    row = cursor.fetchone()
    
    if row:
        target_url = row['target_url']
        
        # 2. 클릭 통계 저장 (접속자 아이피, 브라우저 정보 등)
        client_ip = request.client.host
        user_agent = request.headers.get('user-agent', 'unknown')
        
        cursor.execute(
            'INSERT INTO clicks (qr_short_code, ip_address, user_agent) VALUES (?, ?, ?)',
            (short_code, client_ip, user_agent)
        )
        conn.commit()
        conn.close()
        
        # 3. 원본 구매 URL로 리다이렉트 처리
        return RedirectResponse(url=target_url, status_code=307)
    
    conn.close()
    return {"error": "Invalid or expired QR code"}

if __name__ == "__main__":
    import threading
    import database
    database.init_db()  # 서버 켜질 때 DB 초기화 한번 수행
    print("Starting Redirect Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
