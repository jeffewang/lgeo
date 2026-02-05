import socket
import urllib.request
import urllib.error
import ssl

def check_connection(url):
    print(f"   正在检测: {url} ... ", end="", flush=True)
    try:
        # Create a context that ignores self-signed certs (just in case of proxy issues)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            print(f"✅ 连通 (Code: {response.getcode()})")
            return True
    except urllib.error.URLError as e:
        print(f"❌ 失败 ({e.reason})")
        return False
    except Exception as e:
        print(f"❌ 错误 ({str(e)})")
        return False

def run_diagnostics():
    print("\n🔍 开始网络环境诊断...")
    
    # 1. Basic Internet Check
    print("\n1. 基础网络连通性:")
    check_connection("https://www.baidu.com")
    check_connection("https://www.google.com")
    
    # 2. API Endpoints Check
    print("\n2. 大模型 API 接口检测:")
    endpoints = [
        "https://api.deepseek.com",
        "https://api.moonshot.cn/v1",  # Kimi
        "https://ark.cn-beijing.volces.com/api/v3", # Doubao
        "https://api.hunyuan.cloud.tencent.com/v1" # Yuanbao
    ]
    
    for ep in endpoints:
        check_connection(ep)
        
    print("\n诊断结束。如果只有 Google 失败是正常的；如果 Deepseek/Doubao 等国内接口也失败，说明可能是公司内网防火墙或代理设置问题。")

if __name__ == "__main__":
    run_diagnostics()
