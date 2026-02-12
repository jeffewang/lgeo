import os
import json
import time
from datetime import datetime, timedelta
import sys

# Ensure modules in the current directory can be found when running from root
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from api_client import GenericClient

# Configuration Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def load_config():
    # 1. Load basic structure from file (fallback/local)
    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        # Load from example if real config is missing
        example_path = os.path.join(BASE_DIR, "config.example.json")
        if os.path.exists(example_path):
            with open(example_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
    
    # 2. Override with Environment Variables (GitHub Actions / Cloud)
    # Expected format: PROVIDER_NAME_API_KEY
    if "providers" in config:
        for p_name in config["providers"]:
            env_var_name = f"{p_name.upper()}_API_KEY"
            if env_var_name in os.environ:
                config["providers"][p_name]["api_key"] = os.environ[env_var_name]
                print(f"Loaded API key for {p_name} from environment variable.")
                
    return config

def extract_competitors(answer):
    competitors = ["华为", "小米", "阿里", "腾讯", "百度", "字节", "京东", "海尔", "美的", "比亚迪", "大疆", "宁德时代", "联想"]
    found = []
    for c in competitors:
        if c.lower() in answer.lower():
            found.append(c)
    return list(set(found))

def get_beijing_time():
    """Get current time in Beijing (UTC+8)"""
    return datetime.utcnow() + timedelta(hours=8)

def save_result(intent_name, platform, question, answer, timestamp, strategy_analysis=None, structured_sources=None):
    filename = f"{get_beijing_time().strftime('%Y%m%d')}_results.json"
    filepath = os.path.join(DATA_DIR, filename)
    data = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            try: data = json.load(f)
            except: data = []
            
    is_mentioned = "联想" in answer or "Lenovo" in answer or "lenovo" in answer
    
    # Check for duplicates to avoid appending same result if run multiple times
    # A simple check based on question and platform for today
    # (Optional, but good practice for scheduled tasks)
    
    competitors = extract_competitors(answer)
    
    record = {
        "timestamp": timestamp, "intent": intent_name, "platform": platform,
        "question": question, "answer": answer, "is_mentioned": is_mentioned,
        "competitors": competitors, 
        "sources_v2": structured_sources,
        "geo_strategy": strategy_analysis
    }
    data.append(record)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return is_mentioned

def run_monitoring_task():
    print(f"▶️ Starting Monitoring Task at: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')} (Beijing Time)")
    
    config = load_config()
    # Filter active providers (those with API keys)
    active_providers = [(name, cfg) for name, cfg in config['providers'].items() if cfg.get('api_key')]
    
    if not active_providers:
        print("❌ No active providers found (missing API keys). Exiting.")
        return

    # 1. Generate Questions
    print("🎨 Generating Questions...")
    
    # Use the first available provider for question generation
    gen_name, gen_cfg = active_providers[0]
    client = GenericClient(gen_name, gen_cfg)
    intent_questions = {}
    
    for intent in config['intents']:
        print(f"   Generating for intent: {intent['label']}")
        qs = client.generate_questions(intent['label'], intent['keywords'], count=30) # Default to 30 as in app
        intent_questions[intent['label']] = qs if qs else intent.get('questions', [])[:30]
    
    # 2. Main Loop
    for p_name, p_config in active_providers:
        print(f"📱 Monitoring Platform: {p_name}")
        client = GenericClient(p_name, p_config)
        consecutive_failures = 0
        
        for intent_label, questions in intent_questions.items():
            if consecutive_failures >= 3:
                print(f"⚠️ {p_name} failed too many times, skipping platform.")
                break
                
            print(f"   Processing Intent: {intent_label}")
            
            for q in questions:
                print(f"      Q: {q[:30]}...")
                try:
                    response = client.chat([{"role": "user", "content": q}])
                    if response:
                        consecutive_failures = 0
                        
                        # Extract content from response (it might be a dict or string)
                        answer = ""
                        reasoning = ""
                        if isinstance(response, dict):
                            answer = response.get('content', '')
                            reasoning = response.get('reasoning', '')
                        elif isinstance(response, str):
                            answer = response
                            
                        if not answer:
                            print("      ❌ Empty answer content.")
                            consecutive_failures += 1
                            continue

                        competitors = extract_competitors(answer)
                        structured_srcs = client.extract_structured_sources(answer)
                        strategy = client.analyze_geo_strategy(intent_label, answer, competitors)
                        
                        # Note: save_result might need update if we want to save reasoning too, 
                        # but for now we keep it simple to fix the crash.
                        # If we want to save reasoning, we should update save_result signature or pass it in answer?
                        # run_monitor.py's save_result is different from main.py's save_result.
                        # Let's keep it compatible with existing run_monitor.py save_result for now.
                        
                        save_result(intent_label, p_name, q, answer, get_beijing_time().isoformat(), strategy, structured_srcs)
                        print("      ✅ Saved.")
                    else:
                        print("      ❌ No response.")
                        consecutive_failures += 1
                        if consecutive_failures >= 3: break
                except Exception as e:
                    print(f"      ❌ Error: {e}")
                    import traceback
                    traceback.print_exc()
                    consecutive_failures += 1
                
                time.sleep(1) # Polite delay
                
    print("✅ Monitoring Task Completed Successfully!")

if __name__ == "__main__":
    run_monitoring_task()
