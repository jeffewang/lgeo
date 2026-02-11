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

def test_doubao(api_key, endpoint_id):
    print(f"\n⚡️ 正在验证豆包连通性...")
    print(f"   - API Key: {api_key[:6]}...")
    print(f"   - Endpoint ID: {endpoint_id}")
    
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": endpoint_id,
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            print(f"   ✅ 验证成功! 豆包已连通。")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f"   ❌ 验证失败 (Code: {e.code})")
        print(f"   📄 错误信息: {body}")
        if "AuthenticationError" in body:
            print("   👉 提示: API Key 错误，请检查是否多复制了空格。")
        elif "model_not_found" in body or "endpoint" in body:
            print("   👉 提示: Endpoint ID 错误，请检查是否填成了模型名。")
        return False
    except Exception as e:
        print(f"   ❌ 系统错误: {str(e)}")
        return False

def main():
    print("="*50)
    print("🦈 豆包 (Doubao) 专项配置向导")
    print("="*50)
    print("豆包是最容易配错的，因为它需要两个不同的码：")
    print("1. API Key (用于鉴权)")
    print("2. Endpoint ID (接入点 ID，用于指定模型)")
    print("-" * 50)
    
    # Step 1: API Key
    print("\n👉 第一步：获取 API Key")
    print("   1. 打开 https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey")
    print("   2. 点击【创建 API Key】")
    print("   3. 复制生成的 Key (通常以 b7cd... 开头)")
    api_key = input("\n🔑 请粘贴 API Key: ").strip()
    
    if not api_key:
        print("❌ 未输入 Key，退出。")
        return

    # Step 2: Endpoint ID
    print("\n" + "-" * 50)
    print("👉 第二步：获取 Endpoint ID (接入点)")
    print("   1. 打开 https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint")
    print("   2. 找到一个【状态为运行中】的接入点")
    print("   3. 复制【ID】列的内容 (格式必须是 ep-2024... 这种，不要复制上面的模型名！)")
    endpoint_id = input("\n🔗 请粘贴 Endpoint ID: ").strip()
    
    if not endpoint_id:
        print("❌ 未输入 Endpoint ID，退出。")
        return
        
    if not endpoint_id.startswith("ep-"):
        print(f"\n⚠️  警告: 您输入的 '{endpoint_id}' 看起来不像 Endpoint ID。")
        print("   它应该以 'ep-' 开头。您是否复制错了？")
        confirm = input("   确认要使用这个吗？(y/n): ").strip().lower()
        if confirm != 'y':
            return

    # Step 3: Verify and Save
    if test_doubao(api_key, endpoint_id):
        config = load_config()
        config['providers']['Doubao']['api_key'] = api_key
        config['providers']['Doubao']['model'] = endpoint_id
        config['providers']['Doubao']['enabled'] = True
        save_config(config)
        print("\n🎉 配置已保存！现在可以去运行主程序了。")
    else:
        print("\n❌ 配置验证失败，未保存。请检查上述信息后重试。")

if __name__ == "__main__":
    main()
