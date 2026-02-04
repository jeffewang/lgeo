import os
import json
import pandas as pd
from datetime import datetime, timedelta
from api_client import GenericClient

class BaseSkill:
    def __init__(self, config):
        self.config = config
        # Use the first enabled provider as the default LLM for analysis
        active_providers = [(name, cfg) for name, cfg in config['providers'].items() if cfg.get('api_key')]
        if active_providers:
            self.client = GenericClient(active_providers[0][0], active_providers[0][1])
        else:
            self.client = None

    def execute(self, query, context=None):
        raise NotImplementedError

class DataAnalysisSkill(BaseSkill):
    """
    Skill for analyzing GEO monitoring data.
    """
    def __init__(self, config, data_dir):
        super().__init__(config)
        self.data_dir = data_dir

    def load_recent_data(self, days=7):
        all_records = []
        files = [f for f in os.listdir(self.data_dir) if f.endswith('_results.json')]
        
        # Sort by date to get recent ones
        files.sort(reverse=True)
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for file in files:
            # File format: YYYYMMDD_results.json
            try:
                file_date = datetime.strptime(file.split('_')[0], '%Y%m%d')
                if file_date < cutoff_date:
                    continue
            except:
                pass
                
            with open(os.path.join(self.data_dir, file), 'r', encoding='utf-8') as f:
                try:
                    all_records.extend(json.load(f))
                except:
                    continue
        
        return pd.DataFrame(all_records)

    def execute(self, query, context=None):
        if self.client is None:
            return "错误：未配置 AI 提供商，无法进行数据分析。"

        df = self.load_recent_data()
        if df.empty:
            return "目前没有最近的监测数据可供分析。"

        # Prepare a summary of the data for the LLM
        total_count = len(df)
        mention_rate = (df['is_mentioned'].sum() / total_count * 100) if total_count > 0 else 0
        
        # Get platform breakdown
        platform_stats = df.groupby('platform')['is_mentioned'].mean() * 100
        platform_summary = platform_stats.to_string()
        
        # Get top competitors
        all_comps = [item for sublist in df['competitors'].tolist() if isinstance(sublist, list) for item in sublist]
        from collections import Counter
        top_comps = Counter(all_comps).most_common(5)
        
        # Get intent breakdown
        intent_stats = df.groupby('intent')['is_mentioned'].mean() * 100
        intent_summary = intent_stats.to_string()

        prompt = f"""
        你是一个数据分析专家，负责分析联想集团的 GEO (生成式引擎优化) 监测数据。
        
        以下是最近 7 天的监测数据摘要：
        - 总监测次数: {total_count}
        - 联想总体提及率: {mention_rate:.1f}%
        
        各平台提及率:
        {platform_summary}
        
        各意图提及率:
        {intent_summary}
        
        前 5 大竞争对手提及频率:
        {', '.join([f"{name}({count}次)" for name, count in top_comps])}
        
        用户的分析请求是: "{query}"
        
        请根据以上数据摘要回答用户的问题。如果数据不足以回答，请指出。
        请保持回答专业、简洁，并给出有价值的洞察。
        """

        messages = [{"role": "user", "content": prompt}]
        return self.client.chat(messages)

class SkillManager:
    def __init__(self, config, data_dir):
        self.skills = {
            "data_analysis": DataAnalysisSkill(config, data_dir)
        }

    def handle_query(self, query):
        # For now, we route everything to data_analysis skill
        # In a more complex system, we could use an LLM to route to the right skill
        return self.skills["data_analysis"].execute(query)
