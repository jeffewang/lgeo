import json
import os
from flask import Flask, request, jsonify
from lark_oapi import Client, TokenState
from lark_oapi.api.im.v1 import *
import lark_oapi as lark
from skills import SkillManager

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()
feishu_cfg = config.get("feishu", {})

APP_ID = feishu_cfg.get("app_id", "")
APP_SECRET = feishu_cfg.get("app_secret", "")
VERIFICATION_TOKEN = feishu_cfg.get("verification_token", "")
ENCRYPT_KEY = feishu_cfg.get("encrypt_key", "")

# --- Initialize Skill Manager ---
skill_manager = SkillManager(config, DATA_DIR)

# --- Initialize Feishu Client ---
client = Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .log_level(lark.LogLevel.DEBUG) \
    .build()

app = Flask(__name__)

def send_message(receive_id, receive_id_type, content):
    """
    Send a message back to Feishu.
    """
    msg_content = json.dumps({"text": content})
    request = CreateMessageRequest.builder() \
        .receive_id_type(receive_id_type) \
        .request_body(CreateMessageRequestBody.builder() \
            .receive_id(receive_id) \
            .msg_type("text") \
            .content(msg_content) \
            .build()) \
        .build()
    
    response = client.im.v1.message.create(request)
    if not response.success():
        print(f"Failed to send message: {response.code}, {response.msg}")

@app.route("/callback", methods=["POST"])
def callback():
    # 1. Handle Verification (URL Validation)
    data = request.json
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data.get("challenge")})
    
    # 2. Verify Token (Optional but recommended)
    token = data.get("token")
    if VERIFICATION_TOKEN and token != VERIFICATION_TOKEN:
        return jsonify({"error": "invalid token"}), 403

    # 3. Handle Message Events
    header = data.get("header", {})
    event_type = header.get("event_type")
    
    if event_type == "im.message.receive_v1":
        event = data.get("event", {})
        message = event.get("message", {})
        msg_type = message.get("msg_type")
        
        if msg_type == "text":
            content_raw = message.get("content")
            content_json = json.loads(content_raw)
            text = content_json.get("text", "").strip()
            
            # Remove mention tag if in group chat (e.g., "@Bot text")
            if "@_user_1" in text: # This is a placeholder, actual mention format varies
                text = text.split(" ", 1)[-1] if " " in text else ""
            
            # Get sender info
            sender = event.get("sender", {})
            sender_id = sender.get("sender_id", {}).get("open_id")
            chat_id = message.get("chat_id")
            
            # Process with Skill Manager
            response_text = skill_manager.handle_query(text)
            
            # Send reply
            # If it's a group chat, we might want to reply in the group or to the user
            receive_id = chat_id if chat_id else sender_id
            receive_id_type = "chat_id" if chat_id else "open_id"
            
            send_message(receive_id, receive_id_type, response_text)

    return jsonify({"code": 0, "msg": "success"})

if __name__ == "__main__":
    # In production, use a proper WSGI server like gunicorn
    port = int(os.environ.get("PORT", 5001))
    print(f"Feishu Bot listening on port {port}...")
    app.run(host="0.0.0.0", port=port)
