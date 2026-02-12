import json
import urllib.request
import urllib.error
import time
import ssl

class GenericClient:
    def __init__(self, provider_name, config):
        self.provider_name = provider_name
        self.api_key = config.get('api_key', '')
        self.base_url = config.get('base_url', '')
        self.model = config.get('model', '')
        
        # SSL Context that ignores certificate verification (fixes common local Python issues)
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE
        
        # Adjust base_url if needed (append /chat/completions if not present and not ending with v1/v3 root)
        # Most providers expect base_url to be the root, and client appends /chat/completions
        # But for simplicity, we assume standard OpenAI format: POST {base_url}/chat/completions
        # If base_url ends with /chat/completions, use it as is.
        if not self.base_url.endswith('/chat/completions'):
             self.endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        else:
             self.endpoint = self.base_url

    def is_configured(self):
        return bool(self.api_key) and bool(self.base_url)

    def chat(self, messages, temperature=1.0):
        """
        Send a chat request to OpenAI-compatible API.
        """
        if not self.is_configured():
            print(f"      ⚠️ {self.provider_name} 配置不完整")
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 特殊处理豆包的 Header
        if "volces.com" in self.base_url:
            # 豆包 Ark 平台通常使用标准的 Bearer Token，但需要确保 Endpoint 正确
            pass
            
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
        
        try:
            # 增加超时时间至 120s，以适配 Deepseek R1 等推理模型
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                if 'choices' in result and len(result['choices']) > 0:
                    message = result['choices'][0]['message']
                    content = message.get('content', '')
                    reasoning = message.get('reasoning_content', '') # Capture Deepseek reasoning
                    return {'content': content, 'reasoning': reasoning}
                else:
                    print(f"      ⚠️ {self.provider_name} 返回格式异常: {result}")
                    return None
        except urllib.error.URLError as e:
            # 处理超时错误
            if isinstance(e.reason, time.socket.timeout) or "timed out" in str(e.reason):
                print(f"      ❌ {self.provider_name} 请求超时 (120s)，自动跳过。")
            else:
                print(f"      ❌ {self.provider_name} 连接失败: {str(e.reason)}")
            return None
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"      ❌ {self.provider_name} API 错误 (HTTP {e.code}):")
            print(f"         内容: {error_body}") 
            return None
        except Exception as e:
            print(f"      ❌ {self.provider_name} 未知错误: {str(e)}")
            return None

    def generate_questions(self, intent_label, keywords, count=5):
        """
        Generate diverse questions based on intent.
        """
        prompt = f"""
        你是一个对【{intent_label}】感兴趣的用户。
        请生成 {count} 个搜索问题，核心目的是寻找在这些领域表现优秀的中国公司。
        
        要求：
        1. **核心句式**：主要采用“哪些公司在{intent_label}方面做得好？”、“{intent_label}做得好的公司有哪些？”及其自然变体。
        2. **强制要求信源**：在每个问题后面，必须自然地加上要求，例如“请附上参考链接”、“请列出具体新闻来源”或“有相关报道吗”。这将迫使回答者提供 URL。
        3. **适度发散**：在保持核心句式的基础上，可以稍微变化问法。
        4. **关键词植入**：自然地包含以下关键词之一：{', '.join(keywords)}。
        5. 严禁直接提及“联想”或“Lenovo”。
        6. 每行一个问题，不要带序号。
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = self.chat(messages, temperature=1.0)
        
        if response and response.get('content'):
            raw_text = response['content']
            questions = [line.strip() for line in raw_text.split('\n') if line.strip() and not line[0].isdigit()]
            if not questions:
                questions = [line.strip().lstrip('0123456789. ') for line in raw_text.split('\n') if line.strip()]
            return questions[:count]
        return []

    def analyze_geo_strategy(self, intent_label, answer, competitors):
        """
        Analyze the answer and provide GEO optimization strategy.
        """
        prompt = f"""
        你是一个 GEO (生成式引擎优化) 专家。
        请分析以下大模型关于【{intent_label}】的回答，并给出内容优化建议。
        
        回答内容：
        {answer}
        
        提及的竞对：
        {', '.join(competitors)}
        
        请从以下三个维度给出简短、尖锐的实战建议：
        1. **联想为何未被提及/提及权重不足的原因分析**（从内容缺失、信源权重、关键词关联度等角度猜测）。
        2. **内容优化建议**（联想应该在全网补充什么样的关键词或叙事点）。
        3. **竞争占位策略**（如何针对上述竞对的优势点进行差异化反击）。
        
        要求：直接给出要点，不要废话。
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = self.chat(messages, temperature=0.7)
        if isinstance(response, dict):
            return response.get('content', '')
        return response

    def extract_structured_sources(self, answer):
        """
        Use LLM to extract structured sources (Title, URL, Media).
        """
        prompt = f"""
        请从以下文本中提取所有引用的信源，并以 JSON 数组格式返回。
        如果没有找到任何信源，请返回空数组 []。
        
        文本内容：
        {answer}
        
        JSON 格式要求：
        [
        {{ "title": "文章标题或描述", "url": "完整链接", "media": "媒体名称/域名" }}
        ]
        
        注意：只需返回 JSON，不要任何解释。
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = self.chat(messages, temperature=0.3)
        
        content = ""
        if isinstance(response, dict):
            content = response.get('content', '')
        elif isinstance(response, str):
            content = response
            
        if content:
            try:
                # Find JSON content in case there's markdown wrap
                start = content.find('[')
                end = content.rfind(']') + 1
                if start != -1 and end != -1:
                    return json.loads(content[start:end])
            except:
                pass
        return []
