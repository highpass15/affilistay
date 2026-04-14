from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
app = FastAPI(title="AffiliStay Official")
# 이 부분이 핵심입니다! 사용자님의 클라우드 어드민 주소로 고정합니다.
ADMIN_URL = "https://affilistay-admin.onrender.com"
# 템플릿 및 정적 파일 경로 설정
templates = Jinja2Templates(directory="templates")
static_dir = os.path.join(os.path.dirname(__file__), 'static')
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(
    request=request,
    name="landing.html",
    context={"admin_url": ADMIN_URL}
)
@app.get("/health")
async def health_check():
    return {"status": "ok"}
