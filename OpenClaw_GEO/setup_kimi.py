import json
import os
import ssl
import urllib.request
import urllib.error
import time

# Config Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def test_kimi(api_key):
    print(f"\n⚡️ 正在验证 Kimi 连通性...")
    print(f"   - API Key: {api_key[:6]}...")
    
    url = "https://api.moonshot.cn/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "moonshot-v1-8k",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            print(f"   ✅ 验证成功! Kimi 已连通。")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f"   ❌ 验证失败 (Code: {e.code})")
        print(f"   📄 错误信息: {body}")
        
        if e.code == 429:
             print("   👉 提示: 您的账户余额不足 (insufficient balance)。")
             print("      请前往 https://platform.moonshot.cn/console/info/recharge 充值。")
        elif e.code == 401:
             print("   👉 提示: API Key 无效。请检查是否复制完整，或是否已删除该 Key。")
             
        return False
    except Exception as e:
        print(f"   ❌ 系统错误: {str(e)}")
        return False

def main():
    print("="*50)
    print("🌙 Kimi (Moonshot) 专项配置向导")
    print("="*50)
    print("Kimi 的配置相对简单，只需要一个 API Key。")
    print("-" * 50)
    
    # Step 1: API Key
    print("\n👉 第一步：获取 API Key")
    print("   1. 打开 Kimi 开放平台: https://platform.moonshot.cn/console/api-keys")
    print("   2. 点击【新建】创建一个新的 Key")
    print("   3. 复制 Key (以 sk- 开头)")
    api_key = input("\n🔑 请粘贴 API Key: ").strip()
    
    if not api_key:
        print("❌ 未输入 Key，退出。")
        return

    # Step 2: Verify and Save
    if test_kimi(api_key):
        config = load_config()
        config['providers']['Kimi']['api_key'] = api_key
        config['providers']['Kimi']['enabled'] = True
        save_config(config)
        print("\n🎉 配置已保存！现在可以去运行主程序了。")
    else:
        print("\n❌ 配置验证失败，未保存。请根据上方错误提示（如余额不足）进行处理。")

if __name__ == "__main__":
    main()
