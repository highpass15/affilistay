import subprocess
import re
import time
import os

def start_tunnel():
    print("Starting Cloudflare Tunnel...")
    # Using 'pycloudflared' to run the tunnel
    # The command is normally 'py -m pycloudflared tunnel --url http://localhost:8000'
    process = subprocess.Popen(
        ['py', '-m', 'pycloudflared', 'tunnel', '--url', 'http://localhost:8000'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    public_url = None
    start_time = time.time()
    
    # Wait for the URL to appear in stderr (cloudflared outputs logs to stderr)
    while time.time() - start_time < 30:  # Timeout after 30 seconds
        line = process.stderr.readline()
        if not line:
            break
        print(f"Log: {line.strip()}")
        # Check for the trycloudflare URL pattern
        match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
        if match:
            public_url = match.group(0)
            break
            
    if public_url:
        print(f"\n[FOUND PUBLIC URL] {public_url}")
        with open('public_url.txt', 'w') as f:
            f.write(public_url)
        return public_url
    else:
        print("\n[ERROR] Failed to find public URL in 30 seconds.")
        return None

if __name__ == "__main__":
    start_tunnel()
