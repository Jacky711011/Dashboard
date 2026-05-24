# -*- coding: utf-8 -*-
"""
部署於 Render 的雲端後端核心管線 (含「加入程式」與「查詢ID」完整體)
"""
import os
import json
import base64
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==============================================================================
# 🔐 雲端環境變數安全設定 (由 Render 後台安全注入，不可死寫在代碼中)
# ==============================================================================
GITHUB_TOKEN = os.environ.get("MY_GITHUB_TOKEN")        # 對應 Render 後台的 GitHub 金鑰
REPO_OWNER = os.environ.get("MY_GITHUB_OWNER")          # 對應 Render 後台的 GitHub 帳號
REPO_NAME = os.environ.get("MY_GITHUB_REPO")            # 對應 Render 後台的儲存庫名稱
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN") # 對應 Render 後台的 LINE Bot 金鑰

FILE_PATH = "users.json"

# ==============================================================================
# 🗃️ GitHub 雲端資料庫「跨網路增刪查改」演算法
# ==============================================================================
def get_github_users():
    """ 透過 API 從 GitHub 儲存庫遠端下載最新的用戶名冊 """
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            file_info = res.json()
            sha = file_info["sha"] 
            content = base64.b64decode(file_info["content"]).decode('utf-8')
            return json.loads(content), sha
    except Exception as e:
        print(f"提取 GitHub 資料庫失敗: {e}")
    return {}, None

def save_github_users(data, sha):
    """ 將更新後的名冊重新打包成 Base64 格式，推回 GitHub 覆蓋儲存 """
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    updated_content = json.dumps(data, indent=2, ensure_ascii=False)
    payload = {
        "message": "下單機系統: 自動更新用戶授權名冊狀態",
        "content": base64.b64encode(updated_content.encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    requests.put(url, headers=headers, json=payload, timeout=5)

def push_msg_to_line_user(to_user_id, text_message):
    """ 主動發送 LINE 訊息給特定用戶的 API 封包 """
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": to_user_id,
        "messages": [{"type": "text", "text": text_message}]
    }
    requests.post(url, headers=headers, json=payload, timeout=5)

# ==============================================================================
# 📱 窗口 1：LINE 官方群組 Webhook 監聽路由 (已完美整合「查詢ID」與「加入程式」)
# ==============================================================================
@app.route("/callback", methods=['POST'])
def line_webhook():
    events = request.json.get("events", [])
    for event in events:
        # 確保是用戶發送文字訊息
        if event.get("type") == "message" and event["message"].get("type") == "text":
            user_msg = event["message"]["text"].strip()
            user_id = event["source"].get("userId") # 🎯 抓取用戶唯一的 LINE 加密 ID
            
            if not user_id:
                continue
            
            # 🎯 核心功能一：用戶主動輸入「查詢ID」
            if user_msg == "查詢ID":
                id_reply = f"🔑【您的 LINE 專屬識別碼】\n\n{user_id}\n\n💡 提示：如需續約或開通權限，請直接複製上方這一串 ID 傳給管理員即可唷！"
                push_msg_to_line_user(user_id, id_reply)
                continue # 處理完畢，跳過後續判斷
                
            # 🎯 核心功能二：偵測到「加入程式」關鍵字
            if user_msg == "加入程式":
                users, sha = get_github_users()
                
                if user_id in users:
                    current_expire = users[user_id]['expire_date']
                    push_msg_to_line_user(user_id, f"ℹ️【系統提示】\n您先前已開通。目前授權到期日為：{current_expire}")
                else:
                    # 全自動計算 7 天試用期
                    expire_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                    users[user_id] = {
                        "username": "LINE群組用戶",
                        "expire_date": expire_date,
                        "has_notified_expired": False
                    }
                    save_github_users(users, sha) # 儲存回 GitHub 雲端
                    
                    welcome_msg = f"🎉 恭喜激活成功！\n系統已自動將您的 LINE ID 綁定至雲端授權資料庫。\n\n📊 您已獲得 7 天免費試用權限，訊號將持續接收至：{expire_date}。"
                    push_msg_to_line_user(user_id, welcome_msg)
                    
    return "OK", 200

# ==============================================================================
# 📡 窗口 2：TradingView 雲端訊號轉發（核心權限過濾大閘門）
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def tradingview_webhook():
    tv_data = request.get_json(force=True)
    strategy = tv_data.get("strategy", "未指定策略")
    action = tv_data.get("action", "buy")
    price = tv_data.get("price", "市價")
    symbol = tv_data.get("symbol", "TMF01")
    
    users, sha = get_github_users()
    today_str = datetime.now().strftime("%Y-%m-%d")
    need_update_github = False
    
    for uid, info in list(users.items()):
        expire_date = info["expire_date"]
        
        if today_str <= expire_date:
            signal_msg = f"📡【TV策略實盤訊號轉發】\n策略名稱: {strategy}\n買買動作: {action}\n執行商品: {symbol}\n訊號價格: {price}\n發射時間: {datetime.now().strftime('%H:%M:%S')}"
            push_msg_to_line_user(uid, signal_msg)
        else:
            if not info.get("has_notified_expired", False):
                expired_notice = f"🚨【授權到期公告】\n您的 7 天試用或續約訂閱授權已於 {expire_date} 正式到期！\n系統已自動終止為您轉發任何 TradingView 訊號。如需續約請聯繫官方管理員。"
                push_msg_to_line_user(uid, expired_notice)
                
                users[uid]["has_notified_expired"] = True  
                need_update_github = True
                
    if need_update_github:
        save_github_users(users, sha)
        
    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=6000)
