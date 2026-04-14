import subprocess
import re
import time
import os
import sys

def start_multi_tunnel(ports=[8000, 8501]):
    """
    여러 개의 포트를 각각 개별적인 Cloudflare Tunnel로 외부 공개합니다.
    결과 주소는 public_url_8000.txt, public_url_8501.txt 로 각각 저장됩니다.
    """
    processes = []
    urls = {}
    
    print(f"[*] Starting Multi-Port Cloudflare Tunnels for {ports}...")

    # 각 포트별 프로세스 시작
    for port in ports:
        print(f"[*] Initiating tunnel for port {port}...")
        cmd = ['py', '-m', 'pycloudflared', 'tunnel', '--url', f'http://localhost:{port}']
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        processes.append((port, p))

    # 각 프로세스 로그에서 URL 추출 (최대 60초 대기)
    start_time = time.time()
    while len(urls) < len(ports) and (time.time() - start_time < 60):
        for port, p in processes:
            if port in urls: continue
            
            line = p.stderr.readline()
            if line:
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    found_url = match.group(0)
                    urls[port] = found_url
                    print(f"\n[!] SUCCESS: Port {port} -> {found_url}")
                    
                    # 파일에 개별 저장
                    filename = f'public_url_{port}.txt'
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(found_url)
                    
                    # 하위 호환성을 위해 8000번은 기존 파일명으로도 저장
                    if port == 8000:
                        with open('public_url.txt', 'w', encoding='utf-8') as f:
                            f.write(found_url)

    if len(urls) < len(ports):
        print("\n[!] Warning: Some tunnels failed to start or retrieve URL.")

    # 모든 터널 유지
    print("\n[!] All active tunnels are running. Press Ctrl+C to stop all.")
    try:
        while True:
            time.sleep(10)
            for port, p in processes:
                if p.poll() is not None:
                    print(f"[X] Tunnel for port {port} has died.")
    except KeyboardInterrupt:
        print("\n[*] Terminating all tunnels...")
        for _, p in processes:
            p.terminate()

if __name__ == "__main__":
    # 8000(결제), 8501(어드민) 동시 공개
    start_multi_tunnel([8000, 8501])
