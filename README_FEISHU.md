# OpenClaw GEO 飞书机器人部署指南

本项目已集成飞书机器人功能，并配备了专用的“数据分析 Skills”。

## 功能特性
- **实时对话**：通过飞书与 OpenClaw 机器人进行交互。
- **数据分析 Skill**：机器人可以读取 `data/` 目录下的监测结果，回答如“提及率趋势”、“竞对分析”等问题。
- **自动响应**：支持私聊和群聊提及（@机器人）。

## 部署步骤

### 1. 创建飞书应用
1. 访问 [飞书开放平台](https://open.feishu.cn/)，创建一个企业自建应用。
2. 在“应用功能” -> “机器人”中开启机器人能力。
3. 在“事件订阅”中：
   - 配置请求地址为：`http://你的服务器IP:5001/callback`
   - 添加事件：`接收消息 v2.0` (im.message.receive_v1)
4. 在“权限管理”中勾选以下权限：
   - `im:message` (接收和发送消息)
   - `im:chat` (读取群聊信息)

### 2. 配置 `config.json`
在 `OpenClaw_GEO/config.json` 中填写你的飞书应用凭证：
```json
"feishu": {
  "app_id": "cli_xxxxxxxxxxxx",
  "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxx",
  "verification_token": "xxxxxxxxxxxxxxxxxxxxxxxx"
}
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 启动机器人
```bash
python3 OpenClaw_GEO/feishu_bot.py
```

## 数据分析 Skills 使用示例
在飞书中向机器人发送以下指令：
- “分析一下最近一周的联想提及率趋势。”
- “哪些竞争对手在 AI 意图下表现最活跃？”
- “总结一下目前的 GEO 监测概况。”

## 技术架构
- **feishu_bot.py**: 基于 Flask 的 Web 服务，处理飞书事件回调。
- **skills.py**: 定义分析技能，利用 pandas 处理数据，并调用 LLM 生成深度洞察。
- **api_client.py**: 统一的 AI 调用接口，支持 Deepseek/Kimi/豆包等。
