import json
import os
import ssl
import urllib.request
import urllib.error

# Load config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_provider(name, config):
    print(f"\n⚡️ 正在测试: {name}")
    print(f"   - Endpoint: {config.get('base_url')}")
    print(f"   - Model: {config.get('model')}")
    print(f"   - Key: {config.get('api_key')[:5]}... (Masked)")
    
    if not config.get('api_key'):
        print("   ❌ 跳过 (未配置 Key)")
        return

    # Construct URL
    base_url = config.get('base_url')
    if not base_url.endswith('/chat/completions'):
        url = f"{base_url.rstrip('/')}/chat/completions"
    else:
        url = base_url
        
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.get('api_key')}"
    }
    
    payload = {
        "model": config.get('model'),
        "messages": [{"role": "user", "content": "Hello, verify connection."}],
        "stream": False
    }
    
    # SSL Bypass
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            print(f"   ✅ 连接成功! (Status: {response.getcode()})")
            body = response.read().decode('utf-8')
            print(f"   📄 返回: {body[:100]}...")
    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP 错误 (Code: {e.code})")
        print(f"   📄 错误详情: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"   ❌ 系统错误: {str(e)}")

def main():
    print("🔍 启动 API 连通性深度诊断...")
    config = load_config()
    providers = config.get('providers', {})
    
    for name, p_conf in providers.items():
        if p_conf.get('enabled'):
            test_provider(name, p_conf)

if __name__ == "__main__":
    main()
