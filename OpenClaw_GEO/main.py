#!/usr/bin/env python3
import json
import os
import datetime
from datetime import timedelta
import sys
import time
import threading
import concurrent.futures
from api_client import GenericClient
from check_network import run_diagnostics
from analysis_engine import DeepInsightEngine

# Force unbuffered output for immediate feedback
sys.stdout.reconfigure(line_buffering=True)

# Global Lock for file writing to prevent race conditions
FILE_LOCK = threading.Lock()
PRINT_LOCK = threading.Lock()

import re
from collections import Counter

# Configuration Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def extract_competitors(answer):
    # Common Chinese tech companies/brands
    competitors = [
        "华为", "Huawei", "小米", "Xiaomi", "阿里", "Alibaba", 
        "腾讯", "Tencent", "百度", "Baidu", "字节", "ByteDance",
        "京东", "JD", "海尔", "Haier", "美的", "Midea",
        "比亚迪", "BYD", "大疆", "DJI", "宁德时代", "CATL",
        "联想", "Lenovo" # Include self for comparison
    ]
    found = []
    for c in competitors:
        if c in answer:
            # Normalize english names to Chinese for stats
            norm_name = c
            if c in ["Huawei"]: norm_name = "华为"
            if c in ["Xiaomi"]: norm_name = "小米"
            if c in ["Alibaba"]: norm_name = "阿里"
            if c in ["Tencent"]: norm_name = "腾讯"
            if c in ["Baidu"]: norm_name = "百度"
            if c in ["ByteDance"]: norm_name = "字节"
            if c in ["JD"]: norm_name = "京东"
            if c in ["Haier"]: norm_name = "海尔"
            if c in ["Midea"]: norm_name = "美的"
            if c in ["BYD"]: norm_name = "比亚迪"
            if c in ["DJI"]: norm_name = "大疆"
            if c in ["CATL"]: norm_name = "宁德时代"
            if c in ["Lenovo"]: norm_name = "联想"
            
            found.append(norm_name)
    return list(set(found))

def extract_sources_v2(answer):
    # 提取链接
    urls = re.findall(r'(https?://[^\s\)]+)', answer)
    
    # 媒体名称映射
    media_map = {
        "36kr.com": "36氪",
        "huxiu.com": "虎嗅",
        "sina.com": "新浪",
        "163.com": "网易",
        "sohu.com": "搜狐",
        "caixin.com": "财新",
        "thepaper.cn": "澎湃",
        "jiemian.com": "界面",
        "zhihu.com": "知乎",
        "wikipedia.org": "维基百科"
    }
    
    sources = []
    for url in urls:
        media_name = "其他媒体"
        for domain, name in media_map.items():
            if domain in url:
                media_name = name
                break
        
        sources.append({
            "media": media_name,
            "url": url,
            "title": "相关新闻/报告" 
        })
        
    media_keywords = ["36氪", "虎嗅", "财新", "澎湃", "界面", "晚点", "知乎", "维基百科"]
    for m in media_keywords:
        if m in answer and not any(s['media'] == m for s in sources):
            sources.append({
                "media": m,
                "url": "参考回答文本",
                "title": f"关于{m}的相关报道"
            })
            
    return sources

def get_beijing_time():
    """Get current time in Beijing (UTC+8)"""
    return datetime.datetime.utcnow() + timedelta(hours=8)

def save_result(intent_name, platform, question, result_obj, timestamp):
    # Use Beijing time for filename
    filename = f"{get_beijing_time().strftime('%Y%m%d')}_results.json"
    filepath = os.path.join(DATA_DIR, filename)
    
    answer = result_obj.get('content', '')
    reasoning = result_obj.get('reasoning', '')
    
    data = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except:
                data = []
    
    # Check for Lenovo keywords in answer and reasoning
    is_mentioned = "联想" in answer or "Lenovo" in answer or "lenovo" in answer
    mentioned_in_reasoning = "联想" in reasoning or "Lenovo" in reasoning or "lenovo" in reasoning
    
    # Extract competitors and sources from BOTH answer and reasoning
    competitors_answer = extract_competitors(answer)
    competitors_reasoning = extract_competitors(reasoning)
    all_competitors = list(set(competitors_answer + competitors_reasoning))
    
    sources_answer = extract_sources_v2(answer)
    sources_reasoning = extract_sources_v2(reasoning)
    # Combine source lists carefully (dictionaries cannot be put into set directly)
    # Strategy: Use URL as unique key
    seen_urls = set()
    all_sources = []
    
    for s in sources_answer + sources_reasoning:
        # Use URL as key, but distinguish text-based references by media name
        key = s['url']
        if key == "参考回答文本":
            key = f"{key}_{s['media']}"
            
        if key not in seen_urls:
            all_sources.append(s)
            seen_urls.add(key)
    
    record = {
        "timestamp": timestamp,
        "intent": intent_name,
        "platform": platform,
        "question": question,
        "answer": answer,
        "reasoning": reasoning,
        "is_mentioned": is_mentioned,
        "mentioned_in_reasoning": mentioned_in_reasoning,
        "competitors": all_competitors,
        "sources": [s['media'] for s in all_sources], # Keep backward compatibility for 'sources' field which was list of strings
        "sources_v2": all_sources, # Add new structured field
        "sources_breakdown": {
            "answer": sources_answer,
            "reasoning": sources_reasoning
        },
        "answer_length": len(answer),
        "reasoning_length": len(reasoning)
    }
    
    data.append(record)
    
    with FILE_LOCK:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    return is_mentioned, mentioned_in_reasoning

def generate_report():
    # Find all result files
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('_results.json')]
    all_records = []
    for file in files:
        with open(os.path.join(DATA_DIR, file), 'r', encoding='utf-8') as f:
            all_records.extend(json.load(f))
            
    if not all_records:
        print("\n⚠️  暂无数据，请先执行监测任务。")
        return

    # Calculate stats
    total = len(all_records)
    mentioned = sum(1 for r in all_records if r['is_mentioned'])
    mentioned_cot = sum(1 for r in all_records if r.get('mentioned_in_reasoning') and not r['is_mentioned'])
    rate = (mentioned / total * 100) if total > 0 else 0
    
    print("\n" + "="*60)
    print(f"📊  GEO 深度监测报告 (共 {total} 条数据)")
    print("="*60)
    print(f"✅  联想总体提及率: {rate:.1f}% ({mentioned}/{total})")
    if mentioned_cot > 0:
        print(f"🤔  (另有 {mentioned_cot} 次仅在推理过程中提及，未最终输出)")
    print("-" * 60)
    
    # Get all platforms from config to show full status
    config = load_config()
    all_providers = config.get('providers', {}).keys()
    
    # Existing data platforms
    data_platforms = set(r['platform'] for r in all_records)
    
    # Merge and sort
    platforms = sorted(list(set(list(all_providers) + list(data_platforms))))
    
    for p in platforms:
        p_recs = [r for r in all_records if r['platform'] == p]
        p_total = len(p_recs)
        
        print(f"\n📱 平台: 【{p}】")
        
        if p_total == 0:
             print("    ⚠️  (暂无数据 - 可能未配置 Key 或请求失败)")
             print("-" * 30)
             continue
        
        p_ment = sum(1 for r in p_recs if r['is_mentioned'])
        p_cot = sum(1 for r in p_recs if r.get('mentioned_in_reasoning') and not r['is_mentioned'])
        p_rate = (p_ment / p_total * 100)
        
        print(f"    - 提及率: {p_rate:.1f}% ({p_ment}/{p_total})")
        if p_cot > 0:
            print(f"    - 推理中提及但被过滤: {p_cot} 次")
        print("-" * 30)
        
        # 1. Competitor Analysis for this platform
        p_competitors = []
        for r in p_recs:
            if 'competitors' in r and isinstance(r['competitors'], list): p_competitors.extend(r['competitors'])
        
        print("  🔥 竞品/关联公司排行:")
        if p_competitors:
            for name, count in Counter(p_competitors).most_common(5):
                print(f"     - {name}: {count}")
        else:
            print("     (无数据)")
            
        # 2. Source Analysis for this platform
        p_sources = []
        for r in p_recs:
            if 'sources_v2' in r and isinstance(r['sources_v2'], list):
                p_sources.extend([s['media'] for s in r['sources_v2']])
            elif 'sources' in r and isinstance(r['sources'], list):
                p_sources.extend(r['sources'])
            
        print("\n  📢 引用信源/媒体:")
        if p_sources:
            for name, count in Counter(p_sources).most_common(5):
                print(f"     - {name}: {count}")
        else:
            print("     (无数据)")
    
    print("-" * 60)
    
    # Global Source Recommendation
    print("\n🌟 优质信源推荐 (基于全平台引用权重)")
    all_sources = []
    for r in all_records:
        if 'sources_v2' in r and isinstance(r['sources_v2'], list):
            all_sources.extend([s['media'] for s in r['sources_v2']])
        elif 'sources' in r and isinstance(r['sources'], list):
            all_sources.extend(r['sources'])
    
    if all_sources:
        top_sources = Counter(all_sources).most_common(5)
        print("建议在以下高权重媒体增加内容投放：")
        for name, count in top_sources:
            print(f"  👉 {name} (被引用 {count} 次)")
    else:
        print("  (数据不足，暂无推荐)")
        
    print("="*60 + "\n")

def run_auto_monitor_task():
    config = load_config()
    providers = config.get('providers', {})
    intents = config['intents']
    
    print("\n🚀  启动全平台全自动监测模式 (一键托管版)")
    print("支持平台: " + ", ".join([p for p, c in providers.items() if c['enabled']]))
    print("系统将依次遍历所有平台和意图，无需任何人工干预。\n")
    
    # Check keys first
    active_providers = []
    for p_name, p_config in providers.items():
        if not p_config['enabled']: continue
        
        if not p_config.get('api_key'):
            print(f"\n🔑  请输入 {p_name} API Key (回车跳过):")
            key = input("Key: ").strip()
            if key:
                providers[p_name]['api_key'] = key
                p_config['api_key'] = key # Update local ref
                active_providers.append((p_name, p_config))
            else:
                print(f"⚠️  跳过 {p_name} (无 Key)")
        else:
            active_providers.append((p_name, p_config))
            
    if not active_providers:
        print("❌  没有可用的平台配置。请至少配置一个 API Key。")
        save_config(config) # Save any keys entered
        return
        
    save_config(config) # Save keys
    
    # 1. First, use Deepseek (or the first available robust model) to generate all questions
    # We'll store them in a dictionary: {intent_label: [questions]}
    print("\n" + "="*50)
    print("🎨 正在统一生成监测问题集 (使用 Deepseek 保证质量)")
    print("="*50)
    
    # Find a generator (prefer Deepseek)
    generator_name = "Deepseek" if "Deepseek" in [p[0] for p in active_providers] else active_providers[0][0]
    generator_config = next(p[1] for p in active_providers if p[0] == generator_name)
    generator_client = GenericClient(generator_name, generator_config)
    
    intent_questions = {}
    for intent in intents:
        print(f"   ⏳ 正在为【{intent['label']}】生成问题...")
        qs = generator_client.generate_questions(intent['label'], intent['keywords'], count=30)
        if qs:
            intent_questions[intent['label']] = qs
            print(f"      ✅ 已生成 {len(qs)} 个问题")
        else:
            print(f"      ⚠️ 生成失败，将使用默认问题。")
            intent_questions[intent['label']] = intent.get('questions', [])[:30]

    # 2. Main Loop - Ask each platform the same set of questions
    for p_name, p_config in active_providers:
        print(f"\n" + "="*50)
        print(f"📱 正在监测平台: {p_name}")
        print("="*50)
        
        client = GenericClient(p_name, p_config)
        
        for intent_label, questions in intent_questions.items():
            print(f"\n📂 意图: {intent_label}")
            
            for idx, q in enumerate(questions):
                print(f"   ➡️ 提问 ({idx+1}/{len(questions)}): {q}")
                
                # Simple retry logic
                result = None
                for _ in range(3):
                    result = client.chat([{"role": "user", "content": q}])
                    if result:
                        break
                    time.sleep(2)
                
                if not result:
                    print("   ❌  提问失败，跳过。")
                    continue
                    
                timestamp = datetime.datetime.now().isoformat()
                mentioned, mentioned_in_cot = save_result(intent_label, p_name, q, result, timestamp)
                
                if mentioned:
                    print("      ✅  发现提及！")
                elif mentioned_in_cot:
                     print("      🤔  仅在推理思考中提及 (未输出到结果)")
                else:
                    print("      ❌  未提及")
                
                time.sleep(0.5)
            
    print("\n🎉 所有平台任务执行完毕！正在生成深度分析报告...\n")
    generate_report()

def update_api_keys():
    config = load_config()
    providers = config.get('providers', {})
    
    print("\n🔑  修改 API Key")
    active_list = list(providers.keys())
    for idx, p_name in enumerate(active_list):
        has_key = " (已设置)" if providers[p_name].get('api_key') else " (未设置)"
        print(f"{idx + 1}. {p_name}{has_key}")
    print(f"{len(active_list) + 1}. 返回主菜单")
    
    try:
        choice = int(input("\n请选择要修改的平台数字: ")) - 1
        if choice == len(active_list):
            return
        
        target_p = active_list[choice]
        new_key = input(f"请输入 {target_p} 的新 API Key: ").strip()
        if new_key:
            providers[target_p]['api_key'] = new_key
            save_config(config)
            print(f"✅ {target_p} API Key 已更新！")
        else:
            print("⚠️  未输入内容，取消修改。")
    except:
        print("❌ 输入无效。")

def run_monitor_task():
    config = load_config()
    targets = config['targets']
    intents = config['intents']
    
    print("\n🚀  启动 GEO 监测任务")
    print("请选择要监测的平台:")
    for idx, t in enumerate(targets):
        print(f"{idx + 1}. {t}")
    
    try:
        t_choice = int(input("请输入数字 (例如 1): ")) - 1
        target_platform = targets[t_choice]
    except:
        print("输入无效，默认使用第一个。")
        target_platform = targets[0]

    print(f"\n当前监测平台: 【{target_platform}】")
    print("接下来，系统将依次展示问题。请您将问题复制到大模型中提问，然后将回答粘贴回来。\n")
    
    for intent in intents:
        print(f"\n📂  正在监测意图: {intent['label']}")
        for q in intent['questions']:
            print("\n" + "-"*30)
            print(f"❓  问题: {q}")
            print("-"*30)
            print("👉  请复制上面的问题去提问，然后把回答粘贴在下面 (按 Enter 两次结束输入):")
            
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            answer = "\n".join(lines)
            
            if not answer.strip():
                print("⚠️  跳过此问题 (未输入回答)")
                continue
                
            timestamp = datetime.datetime.now().isoformat()
            mentioned = save_result(intent['label'], target_platform, q, answer, timestamp)
            
            if mentioned:
                print("✅  监测到提及！")
            else:
                print("❌  未提及。")

def main():
    print("\n正在初始化系统，请稍候...", flush=True)
    while True:
        print("\n" + "#"*40)
        print("   联想集团 GEO 优化系统 (OpenClaw Lite)")
        print("#"*40)
        print("1. ⚡️  一键启动全平台全自动监测 (Deepseek/Kimi/Doubao/Yuanbao)")
        print("2. ▶️   手动辅助监测 (人工输入模式)")
        print("3. 📊  查看分析报告")
        print("4. 🧠  深度洞察分析 (v2.3 新功能)")
        print("5. 🔍  网络环境诊断")
        print("6. 🔑  修改/设置 API Key")
        print("7. ❌  退出")
        
        choice = input("\n请选择功能 (1-7): ")
        
        if choice == '1':
            run_auto_monitor_task()
        elif choice == '2':
            run_monitor_task()
        elif choice == '3':
            generate_report()
        elif choice == '4':
            engine = DeepInsightEngine()
            engine.run()
        elif choice == '5':
            run_diagnostics()
        elif choice == '6':
            update_api_keys()
        elif choice == '7':
            print("再见！")
            sys.exit(0)
        else:
            print("无效输入，请重试。")

if __name__ == "__main__":
    main()
