import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
from datetime import datetime
from api_client import GenericClient
import time
import re
from collections import Counter

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- Helper Functions ---
def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def extract_competitors(answer):
    competitors = ["华为", "小米", "阿里", "腾讯", "百度", "字节", "京东", "海尔", "美的", "比亚迪", "大疆", "宁德时代", "联想"]
    found = []
    for c in competitors:
        if c.lower() in answer.lower():
            found.append(c)
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
        
        # 尝试从 URL 前后提取“标题” (启发式：取链接前 15 个字或后 15 个字作为上下文)
        # 这里为了演示，我们先提取媒体名和链接
        sources.append({
            "media": media_name,
            "url": url,
            "title": "相关新闻/报告" # 简化处理，因为大模型回答中标题提取较难
        })
        
    # 如果没有链接但提到了媒体名
    media_keywords = ["36氪", "虎嗅", "财新", "澎湃", "界面", "晚点", "知乎", "维基百科"]
    for m in media_keywords:
        if m in answer and not any(s['media'] == m for s in sources):
            sources.append({
                "media": m,
                "url": "参考回答文本",
                "title": f"关于{m}的相关报道"
            })
            
    return sources

def save_result(intent_name, platform, question, answer, timestamp, strategy_analysis=None, structured_sources=None):
    filename = f"{datetime.now().strftime('%Y%m%d')}_results.json"
    filepath = os.path.join(DATA_DIR, filename)
    data = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            try: data = json.load(f)
            except: data = []
    is_mentioned = "联想" in answer or "Lenovo" in answer or "lenovo" in answer
    
    # 竞对提取
    competitors = extract_competitors(answer)
    
    record = {
        "timestamp": timestamp, "intent": intent_name, "platform": platform,
        "question": question, "answer": answer, "is_mentioned": is_mentioned,
        "competitors": competitors, 
        "sources_v2": structured_sources if structured_sources else extract_sources_v2(answer),
        "geo_strategy": strategy_analysis
    }
    data.append(record)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return is_mentioned

# --- Streamlit UI ---
st.set_page_config(page_title="联想集团 GEO 优化系统", layout="wide")

# 隐藏 Streamlit 原生菜单和按钮，并增强文字对比度
st.markdown("""
    <style>
    #MainMenu {display: none !important;}
    footer {display: none !important;}
    .stAppDeployButton {display: none !important;}
    
    /* 强制增强文字颜色 */
    h1, h2, h3, p, span, label, .stMarkdown {
        color: #31333F !important;
    }
    
    /* 仪表盘卡片数字颜色 */
    [data-testid="stMetricValue"] {
        color: #0E1117 !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 联想集团 GEO 优化系统 (OpenClaw GUI)")

# --- Sidebar: Monitoring Control ---
with st.sidebar:
    st.header("🛰️ 监测控制台")
    config = load_config()
    active_providers = [(name, cfg) for name, cfg in config['providers'].items() if cfg.get('api_key')]
    
    if "is_running" not in st.session_state:
        st.session_state.is_running = False

    if not st.session_state.is_running:
        if st.button("🚀 开启全自动监测", use_container_width=True):
            if not active_providers:
                st.error("请先设置 API 密钥！")
            else:
                st.session_state.is_running = True
                st.rerun()
    else:
        if st.button("🛑 停止监测任务", use_container_width=True):
            st.session_state.is_running = False
            st.rerun()

    st.markdown("---")
    st.subheader("实时日志")
    log_placeholder = st.empty()
    if "logs" not in st.session_state:
        st.session_state.logs = []
    log_placeholder.code("\n".join(st.session_state.logs[-15:]) if st.session_state.logs else "等待任务启动...")

# --- Main Tabs ---
tab1, tab2 = st.tabs(["📊 实时仪表盘", "⚙️ 系统配置"])

# --- Tab 2: Configuration ---
with tab2:
    st.header("系统设置")
    config = load_config()
    st.subheader("API 密钥配置")
    for p_name, p_config in config['providers'].items():
        col1, col2 = st.columns([1, 3])
        with col1:
            st.write(f"**{p_name}**")
        with col2:
            new_key = st.text_input(f"{p_name} 的 API 密钥", value=p_config.get('api_key', ''), type="password", key=f"key_{p_name}")
            config['providers'][p_name]['api_key'] = new_key
    
    if st.button("保存配置"):
        save_config(config)
        st.success("配置已保存！")

# --- Tab 1: Dashboard ---
with tab1:
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('_results.json')]
    all_data = []
    for f in files:
        with open(os.path.join(DATA_DIR, f), 'r', encoding='utf-8') as file:
            all_data.extend(json.load(file))
    
    if not all_data:
        st.info("暂无监测数据，请先在左侧启动监测任务。")
    else:
        df = pd.DataFrame(all_data)
        
        # Overview Cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总监测次数", len(df))
        with col2:
            mention_rate = (df['is_mentioned'].sum() / len(df)) * 100
            st.metric("联想提及率", f"{mention_rate:.1f}%")
        with col3:
            st.metric("覆盖意图数", df['intent'].nunique())
            
        # Charts
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("各平台提及率对比")
            platform_stats = df.groupby('platform')['is_mentioned'].mean().reset_index()
            platform_stats['is_mentioned'] *= 100
            fig = px.bar(platform_stats, x='platform', y='is_mentioned', 
                         labels={'platform': '监测平台', 'is_mentioned': '提及率 (%)'},
                         title='各平台联想提及率对比')
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.subheader("热门竞品排行")
            # 过滤掉非列表的数据（处理历史遗留数据或异常数据）
            all_comps = [item for sublist in df['competitors'].tolist() if isinstance(sublist, list) for item in sublist]
            comp_df = pd.DataFrame(Counter(all_comps).most_common(10), columns=['公司', '次数'])
            fig2 = px.pie(comp_df, values='次数', names='公司', title='竞品提及频率分析')
            st.plotly_chart(fig2, use_container_width=True)
            
        # --- 意图深度透视 ---
        st.markdown("---")
        st.header("🎯 意图深度透视")
        
        selected_intent = st.selectbox("选择要分析的意图", df['intent'].unique())
        intent_df = df[df['intent'] == selected_intent]
        
        # 1. 意图概览指标
        i_col1, i_col2, i_col3 = st.columns(3)
        with i_col1:
            st.metric(f"【{selected_intent}】监测次数", len(intent_df))
        with i_col2:
            i_mention_rate = (intent_df['is_mentioned'].sum() / len(intent_df)) * 100
            st.metric("联想在该意图下的提及率", f"{i_mention_rate:.1f}%")
        with i_col3:
            i_comps_all = [item for sublist in intent_df['competitors'].tolist() if isinstance(sublist, list) for item in sublist]
            top_comp = Counter(i_comps_all).most_common(1)[0][0] if i_comps_all else "暂无"
            st.metric("该意图头号竞争对手", top_comp)

        # 2. 图表排布优化
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("📊 竞对提及分布")
            if i_comps_all:
                i_comp_df = pd.DataFrame(Counter(i_comps_all).most_common(10), columns=['公司', '出现次数'])
                fig_i = px.bar(i_comp_df, x='公司', y='出现次数', color='出现次数', 
                               text_auto=True, color_continuous_scale='Reds')
                fig_i.update_layout(showlegend=False, plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_i, use_container_width=True)
            else:
                st.write("该意图下暂无竞对数据")
                
        with col_right:
            st.subheader("🔗 优质信源分布")
            i_srcs = []
            for r in intent_df.to_dict('records'):
                if 'sources_v2' in r and isinstance(r['sources_v2'], list):
                    i_srcs.extend(r['sources_v2'])
                elif 'sources' in r and isinstance(r['sources'], list):
                    for s in r['sources']:
                        i_srcs.append({"media": s, "url": "-", "title": "历史数据"})
            
            if i_srcs:
                i_src_df = pd.DataFrame(i_srcs)
                i_src_df['media'] = i_src_df['media'].fillna('未知信源').replace('', '未知信源')
                media_counts = i_src_df['media'].value_counts().reset_index()
                media_counts.columns = ['媒体名', '引用次数']
                
                fig_src_i = px.bar(media_counts.head(10), x='引用次数', y='媒体名', orientation='h',
                                   color='引用次数', color_continuous_scale='Viridis', text='引用次数')
                fig_src_i.update_traces(textposition='outside')
                fig_src_i.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_src_i, use_container_width=True)
            else:
                st.write("该意图下暂无信源数据")

        # 3. 策略与详情下沉
        st.markdown("---")
        strat_col, table_col = st.columns([1, 1])
        
        with strat_col:
            st.subheader("💡 GEO 内容优化建议")
            if 'geo_strategy' in intent_df.columns:
                latest_strategy = intent_df.dropna(subset=['geo_strategy']).sort_values('timestamp', ascending=False)
                if not latest_strategy.empty:
                    st.info(latest_strategy.iloc[0]['geo_strategy'])
                else:
                    st.write("暂无 AI 策略建议。")
            else:
                st.write("历史数据暂无策略建议。")
        
        with table_col:
            st.subheader("📑 引用信源详情")
            if i_srcs:
                st.dataframe(pd.DataFrame(i_srcs)[['media', 'title', 'url']].head(20), use_container_width=True)
            else:
                st.write("暂无详情。")
        
        st.markdown("---")
        st.subheader("🔥 全平台优质信源排行榜 (全意图汇总)")
        # 兼容处理全量信源
        all_srcs_v2 = []
        for r in df.to_dict('records'):
            if 'sources_v2' in r and isinstance(r['sources_v2'], list):
                for s in r['sources_v2']:
                    all_srcs_v2.append(s['media'])
            elif 'sources' in r and isinstance(r['sources'], list):
                all_srcs_v2.extend(r['sources'])
                
        if all_srcs_v2:
            # 清洗数据：处理空字符串和 None
            cleaned_srcs = [s if s and s.strip() else "未知/通用信源" for s in all_srcs_v2]
            src_counts = pd.DataFrame(Counter(cleaned_srcs).most_common(10), columns=['信源', '出现次数'])
            
            # 绘制全局信源排行图
            fig_src_global = px.bar(src_counts, x='出现次数', y='信源', orientation='h',
                                    title='全平台引用频次最高的 Top 10 信源',
                                    color='出现次数', 
                                    color_continuous_scale='Plasma',
                                    text='出现次数') # 显示具体次数
            fig_src_global.update_traces(textposition='outside')
            fig_src_global.update_layout(
                yaxis={'categoryorder':'total ascending'},
                margin=dict(l=20, r=20, t=40, b=20),
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_src_global, use_container_width=True)
            
            with st.expander("查看信源数据详情"):
                st.table(src_counts)
        else:
            st.write("暂无信源统计数据")

# --- Background Task Runner ---
if st.session_state.is_running:
    st.session_state.logs.append(f"▶️ 监测任务启动时间: {datetime.now().strftime('%H:%M:%S')}")
    
    config = load_config()
    active_providers = [(name, cfg) for name, cfg in config['providers'].items() if cfg.get('api_key')]
    
    # 1. Generate Questions
    st.session_state.logs.append("🎨 正在统一生成监测问题集...")
    log_placeholder.code("\n".join(st.session_state.logs[-15:]))
    
    gen_name, gen_cfg = active_providers[0]
    client = GenericClient(gen_name, gen_cfg)
    intent_questions = {}
    for intent in config['intents']:
        qs = client.generate_questions(intent['label'], intent['keywords'], count=30)
        intent_questions[intent['label']] = qs if qs else intent.get('questions', [])[:30]
    
    # 2. Main Loop
    total_tasks = len(active_providers) * len(intent_questions)
    task_count = 0
    
    for p_name, p_config in active_providers:
        if not st.session_state.is_running: break
        
        client = GenericClient(p_name, p_config)
        consecutive_failures = 0
        
        for intent_label, questions in intent_questions.items():
            if not st.session_state.is_running: break
            if consecutive_failures >= 3:
                st.session_state.logs.append(f"⚠️ {p_name} 连续失败过多，跳过该平台。")
                break
                
            st.session_state.logs.append(f"📱 监测平台: {p_name} | 意图: {intent_label}")
            log_placeholder.code("\n".join(st.session_state.logs[-15:]))
            
            for q in questions:
                if not st.session_state.is_running: break
                answer = client.chat([{"role": "user", "content": q}])
                if answer:
                    consecutive_failures = 0
                    competitors = extract_competitors(answer)
                    structured_srcs = client.extract_structured_sources(answer)
                    strategy = client.analyze_geo_strategy(intent_label, answer, competitors)
                    save_result(intent_label, p_name, q, answer, datetime.now().isoformat(), strategy, structured_srcs)
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 3: break
                time.sleep(0.5)
            
            task_count += 1
            # 关键：每完成一个意图，刷新一次 UI 展现最新数据
            st.rerun()
            
    st.session_state.is_running = False
    st.session_state.logs.append("✅ 监测任务已圆满完成！")
    st.rerun()
