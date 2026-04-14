from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from database import get_db_connection
import os

app = FastAPI(title="Minoan Style Platform")

def get_public_url(port):
    filename = f'public_url_{port}.txt'
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return f"http://localhost:{port}"

# 정적 파일(이미지 등) 서비스 설정
static_dir = os.path.join(os.path.dirname(__file__), 'static')
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
templates = Jinja2Templates(directory=template_dir)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    ADMIN_URL = get_public_url(8501)
    return templates.TemplateResponse(
        request=request, name="landing.html", context={"admin_url": ADMIN_URL}
    )

@app.get("/buy/{qr_code_id}", response_class=HTMLResponse)
async def view_checkout_page(request: Request, qr_code_id: str):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE qr_code_id = ?', (qr_code_id,)).fetchone()
    conn.close()
    
    if not product:
        return HTMLResponse(content="<h1>만료되거나 유효하지 않은 QR 코드입니다.</h1>", status_code=404)
        
    return templates.TemplateResponse(
        request=request, name="checkout.html", context={"product": dict(product)}
    )

@app.post("/pay/{qr_code_id}", response_class=HTMLResponse)
async def process_mock_payment(
    qr_code_id: str,
    customer_name: str = Form(...),
    phone_number: str = Form(...),
    shipping_address: str = Form(...)
):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE qr_code_id = ?', (qr_code_id,)).fetchone()
    
    if not product:
        conn.close()
        return HTMLResponse(content="결제 실패: 유효하지 않은 상품", status_code=400)
    
    conn.execute('''
        INSERT INTO orders (product_id, customer_name, phone_number, shipping_address, total_amount)
        VALUES (?, ?, ?, ?, ?)
    ''', (product['id'], customer_name, phone_number, shipping_address, product['price']))
    
    conn.commit()
    conn.close()
    
    success_html = f"""
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="font-family:'Inter', sans-serif; text-align:center; padding-top:20%; background-color:#FAF9F6; color:#1A1A1A;">
        <h1 style="font-weight:200; font-size:2rem; letter-spacing:0.1em;">THANK YOU.</h1>
        <p style="font-size:0.9rem; color:#666;">전달해주신 배송지로 신속히 보내드리겠습니다.</p>
        <div style="margin-top:2rem;">
            <a href="/" style="text-decoration:none; font-size:0.7rem; color:#A89F91; border-bottom:1px solid #A89F91;">BACK TO HOME</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=success_html)

if __name__ == "__main__":
    import database
    database.init_db()
    print("[SERVER] Minoan Style Web Server is running on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
