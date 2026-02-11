import json
import os
from collections import Counter
from api_client import GenericClient

# Load config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

class DeepInsightEngine:
    def __init__(self):
        self.config = load_config()
        # Prefer Deepseek for analysis, otherwise use the first available enabled provider
        self.client = self._get_best_client()

    def _get_best_client(self):
        providers = self.config.get('providers', {})
        
        # Priority 1: Deepseek (Best reasoning)
        if providers.get('Deepseek', {}).get('enabled') and providers['Deepseek'].get('api_key'):
            return GenericClient('Deepseek', providers['Deepseek'])
            
        # Priority 2: Kimi (Good context window)
        if providers.get('Kimi', {}).get('enabled') and providers['Kimi'].get('api_key'):
            return GenericClient('Kimi', providers['Kimi'])
            
        # Fallback: Any enabled provider
        for name, p_conf in providers.items():
            if p_conf.get('enabled') and p_conf.get('api_key'):
                return GenericClient(name, p_conf)
        
        return None

    def load_latest_data(self):
        if not os.path.exists(DATA_DIR):
            return []
        
        files = [f for f in os.listdir(DATA_DIR) if f.endswith('_results.json')]
        if not files:
            return []
            
        # Sort by date, latest first
        files.sort(reverse=True)
        latest_file = files[0]
        
        print(f"📂 加载最新数据文件: {latest_file}")
        with open(os.path.join(DATA_DIR, latest_file), 'r', encoding='utf-8') as f:
            return json.load(f)

    def analyze_gap(self, intent, records):
        """
        Analyze why competitors are mentioned but Lenovo is not.
        """
        # Filter records where Lenovo is NOT mentioned but others ARE
        gap_records = [r for r in records if not r['is_mentioned'] and r.get('competitors')]
        
        if not gap_records:
            return None

        # Summarize the context for LLM
        competitor_mentions = []
        sample_answers = []
        
        all_comps = []
        for r in gap_records:
            all_comps.extend(r.get('competitors', []))
            if len(sample_answers) < 3: # Take top 3 examples
                sample_answers.append(f"Q: {r['question']}\nA: {r['answer'][:200]}...")

        top_competitors = [c[0] for c in Counter(all_comps).most_common(5)]
        
        prompt = f"""
        你是一个 GEO (生成式引擎优化) 战略专家。
        我们正在分析【{intent}】这个领域的搜索结果。
        
        现状数据：
        1. 在这些问题中，大模型频繁推荐了竞品：{', '.join(top_competitors)}。
        2. 但是，【联想 (Lenovo)】完全未被提及。
        
        以下是几个典型的回答片段（大模型认为好的答案）：
        {json.dumps(sample_answers, ensure_ascii=False, indent=2)}
        
        请进行深度差异分析 (Gap Analysis)：
        1. **核心差距**：为什么大模型觉得竞品在{intent}方面比联想好？竞品赢在哪些具体的叙事点（例如：特定技术、具体案例、社会影响力）？
        2. **关键词雷达**：竞品被提及的高频“褒义词”或“场景词”有哪些？(列出 5 个)
        3. **反击策略**：联想应该补充哪些类型的网络内容，才能让大模型在下次回答时收录联想？
        
        输出要求：
        - 风格犀利直接，不要套话。
        - 使用 Markdown 格式，分点陈述。
        """
        
        print(f"   🤖 正在调用大模型分析【{intent}】的差距...")
        response = self.client.chat([{"role": "user", "content": prompt}], temperature=0.7)
        
        # Handle dict response (new api_client format)
        if isinstance(response, dict):
            return response.get('content', '')
        return response

    def run(self):
        if not self.client:
            print("❌ 无法启动分析引擎：未配置有效的 API Key。")
            return

        data = self.load_latest_data()
        if not data:
            print("❌ 未找到监测数据，请先运行监测任务。")
            return

        print("\n🧠 启动 GEO 深度洞察引擎 (v2.3)")
        print("="*60)
        
        report_content = f"# GEO 深度洞察报告 (v2.3)\n生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Group by intent
        intents = set(r['intent'] for r in data)
        
        for intent in intents:
            print(f"\n📂 正在分析意图板块: {intent}")
            intent_records = [r for r in data if r['intent'] == intent]
            
            # 1. Basic Stats
            total = len(intent_records)
            mentioned = sum(1 for r in intent_records if r['is_mentioned'])
            stats_line = f"   - 数据量: {total} 条 | 联想提及率: {mentioned/total:.1%}"
            print(stats_line)
            
            report_content += f"## 📂 意图: {intent}\n{stats_line}\n\n"
            
            # 2. Gap Analysis
            if mentioned / total < 0.8: # If mention rate is below 80%, analyze gap
                analysis = self.analyze_gap(intent, intent_records)
                
                if analysis:
                    print(f"\n💡 【深度洞察报告】")
                    print("-" * 40)
                    print(analysis)
                    print("-" * 40)
                    
                    report_content += f"### 💡 差距分析与建议\n{analysis}\n\n---\n\n"
                else:
                    print("   (数据不足以进行差距分析)")
            else:
                msg = "   🎉 表现优异！在此意图下联想已占据主导地位，无需额外分析。"
                print(msg)
                report_content += f"{msg}\n\n"

        # Save report to file
        import datetime
        filename = f"GEO_INSIGHT_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(BASE_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
            
        print(f"\n📄 完整分析报告已生成: {filename}")
        print("   (您可以直接在编辑器中打开查看)")

if __name__ == "__main__":
    engine = DeepInsightEngine()
    engine.run()
