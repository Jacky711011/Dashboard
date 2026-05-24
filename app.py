# -*- coding: utf-8 -*-
"""
部署於 Render 的雲端後端核心管線 (加入程式 + 訂閱預約雙軌制完全體)
"""
import os
import json
import base64
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==============================================================================
# 🔐 雲端環境變數安全設定
# ==============================================================================
GITHUB_TOKEN = os.environ.get("MY_GITHUB_TOKEN")
REPO_OWNER = os.environ.get("MY_GITHUB_OWNER")
REPO_NAME = os.environ.get("MY_GITHUB_REPO")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")

FILE_PATH = "users.json"

def get_github_users():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            file_info = res.json()
            sha = file_info["sha"] 
            content = base64.b64decode(file_info["content"]).decode('utf-8')
            return json.loads(content), sha
    except Exception as e:
        print(f"提取 GitHub 失敗: {e}")
    return {}, None

def save_github_users(data, sha):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"}
    updated_content = json.dumps(data, indent=2, ensure_ascii=False)
    payload = {
        "message": "下單機系統: 自動更新用戶授權狀態",
        "content": base64.b64encode(updated_content.encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    requests.put(url, headers=headers, json=payload, timeout=5)

def push_msg_to_line_user(to_user_id, text_message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
    payload = {"to": to_user_id, "messages": [{"type": "text", "text": text_message}]}
    try: requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception as e: print(f"LINE 發送異常: {e}")

# ==============================================================================
# 📱 窗口 1：LINE Webhook 監聽核心邏輯 (加入程式、訂閱、查詢ID完美並存)
# ==============================================================================
@app.route("/callback", methods=['POST'])
def line_webhook():
    events = request.json.get("events", [])
    for event in events:
        if event.get("type") == "message" and event["message"].get("type") == "text":
            user_msg = event["message"]["text"].strip()
            user_id = event["source"].get("userId")
            
            if not user_id:
                continue
            
            # 🎯 功能一：用戶主動輸入「查詢ID與到期時間」
            if user_msg == "查詢ID":
                users, sha = get_github_users()
                if user_id in users:
                    expire_date = users[user_id]['expire_date']
                    sub_status = users[user_id].get("sub_status", "已訂閱")
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    
                    if sub_status == "待處理":
                        status_note = "🟡 訂閱申請審核中\n⚠️ 提示：請等待管理員聯繫您開通。"
                    elif today_str <= expire_date:
                        status_note = f"🟢 正常接收訊號中\n📅 授權到期日：{expire_date}"
                    else:
                        status_note = f"🚨 授權已到期\n📅 截止到期日：{expire_date}\n⚠️ 提示：訊號已自動終止。"
                        
                    id_reply = f"🔑【您的 LINE 帳號狀態】\n\n👤 識別碼：\n{user_id}\n\n📊 訂閱狀態：\n{status_note}"
                else:
                    id_reply = f"🔑【您的 LINE 專屬識別碼】\n\n{user_id}\n\n❌ 授權狀態：尚未開通\n💡 提示：輸入「加入程式」可開通免費試用，或輸入「訂閱」送出續約預約申請！"
                
                push_msg_to_line_user(user_id, id_reply)
                continue
                
            # 🎯 功能二：用戶打「加入程式」➔ 自動開通 7 天免費試用期 (幫你加回來了！)
            if user_msg == "加入程式":
                users, sha = get_github_users()
                if user_id in users:
                    current_expire = users[user_id]['expire_date']
                    push_msg_to_line_user(user_id, f"ℹ️【系統提示】\n您先前已加入過名冊。目前授權到期日為：{current_expire}")
                else:
                    # 全自動計算 7 天試用期，預設開通狀態為「已訂閱」放行訊號
                    expire_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                    users[user_id] = {
                        "username": "LINE試用戶",
                        "expire_date": expire_date,
                        "sub_status": "已訂閱",
                        "has_notified_expired": False
                    }
                    save_github_users(users, sha)
                    
                    welcome_msg = f"🎉 恭喜激活成功！\n系統已自動將您的 LINE ID 綁定至雲端授權資料庫。\n\n📊 您已獲得 7 天免費試用權限，訊號將持續接收至：{expire_date}。"
                    push_msg_to_line_user(user_id, welcome_msg)
                continue

            # 🎯 功能三：用戶主動輸入「訂閱」➔ 填單等待管理員聯繫核帳
            if user_msg == "訂閱":
                users, sha = get_github_users()
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                if user_id in users:
                    current_status = users[user_id].get("sub_status", "已訂閱")
                    if current_status == "待處理":
                        push_msg_to_line_user(user_id, "ℹ️【系統提示】\n您先前已送出過訂閱申請，目前正在「待處理」審核階段，請耐心等候管理員與您聯繫唷！")
                    else:
                        # 已開通用戶打訂閱代表想續約，洗回「待處理」
                        users[user_id]["sub_status"] = "待處理"
                        save_github_users(users, sha)
                        push_msg_to_line_user(user_id, f"🔄【續約申請成功】\n已幫您提報續約申請！\n管理員將會儘速與您確認後續收費事宜。\n\n👤 您的識別碼：\n{user_id}")
                else:
                    # 全新客戶未試用直接買，狀態給予「待處理」不放行訊號，等管理員手動加天數
                    users[user_id] = {
                        "username": "新申請用戶",
                        "expire_date": today_str,
                        "sub_status": "待處理",
                        "has_notified_expired": False
                    }
                    save_github_users(users, sha)
                    
                    welcome_msg = f"📩【訂閱申請已送出】\n恭喜您！系統已成功將您的預約資料提報至雲端。\n\n🕵️ 管理員將會親自與您聯繫，提供詳細的匯款與收費管道，確認後將立刻幫您開通實盤訊號權限！\n\n👤 您的專屬識別碼：\n{user_id}"
                    push_msg_to_line_user(user_id, welcome_msg)
                    
    return "OK", 200

# ==============================================================================
# 📡 窗口 2：TradingView 訊號過濾大閘門
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
        sub_status = info.get("sub_status", "已訂閱")
        
        # 🔒 只有狀態是 "已訂閱"，且今天還沒到期的，才放行發送訊號！
        if sub_status == "已訂閱" and today_str <= expire_date:
            signal_msg = f"📡【TV策略實盤訊號轉發】\n策略名稱: {strategy}\n買賣動作: {action}\n執行商品: {symbol}\n訊號價格: {price}\n發射時間: {datetime.now().strftime('%H:%M:%S')}"
            push_msg_to_line_user(uid, signal_msg)
        else:
            if sub_status == "已訂閱" and today_str > expire_date and not info.get("has_notified_expired", False):
                expired_notice = f"🚨【授權到期公告】\n您的授權已於 {expire_date} 正式到期！系統已自動終止訊號轉發，如需續約請在聊天室打「訂閱」聯繫管理員。"
                push_msg_to_line_user(uid, expired_notice)
                users[uid]["has_notified_expired"] = True  
                need_update_github = True
                
    if need_update_github:
        save_github_users(users, sha)
        
    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=6000)
