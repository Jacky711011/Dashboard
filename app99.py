from flask import Flask, request, jsonify
import json
import requests
import os
import base64
from datetime import datetime
import pytz

app = Flask(__name__)

# ==========================================
# 🎫 1. 雲端安全性與 GitHub 儲存庫設定
# ==========================================
#  修改後的安全寫法：

# 直接把後面的明文砍掉，只留下這純淨的一行：
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO = "Jacky711011/Dashboard"
FILE_PATH = "market_status.json"

# ==========================================
# 🔔 2. LINE Bot 金鑰與管理員設定
# ==========================================
LINE_ACCESS_TOKEN = 'FMmKijyWSUloSPnRYV7GwnQrZDV9oNojPkP5mEGhlklcanN3j1aqI/FXPlFULIN+UMLhDRlnw1NV96X6X2P6j8sV48rbz362otHnnZTxYbtJzzO1j2BElT+O/CzOFdQ8nI2DnJrx9NxpLgAFqfsXMwdB04t89/1O/w1cDnyilFU='
OWNER_USER_ID = "U58d27a73dfc776512e42e948769bb082"

USER_SUB_FILE = 'user_subscriptions.json'

# --- 💾 買斷制資料庫讀寫機關 ---
def load_user_subscriptions():
    if not os.path.exists(USER_SUB_FILE): return {}
    try:
        with open(USER_SUB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_user_subscriptions(data):
    with open(USER_SUB_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

def verify_lifetime_user(user_id):
    """ 智慧特權驗證：如果是老闆本人或已授權的買斷用戶，即刻放行 """
    if user_id == OWNER_USER_ID: return True
    subs = load_user_subscriptions()
    if user_id in subs:
        return subs[user_id].get("is_lifetime_active", False)
    return False

# --- 🚀 LINE 官方通訊發射台 ---
def reply_message(reply_token, text):
    url = 'https://api.line.me/v2/bot/message/reply'
    headers = {'Authorization': f'Bearer {LINE_ACCESS_TOKEN}', 'Content-Type': 'application/json'}
    data = {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]}
    requests.post(url, headers=headers, json=data)

def send_line_message(text):
    """ 負責主動推播即時策略訊號至你手機的靈魂函數 """
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {'Authorization': f'Bearer {LINE_ACCESS_TOKEN}', 'Content-Type': 'application/json'}
    data = {"to": OWNER_USER_ID, "messages": [{"type": "text", "text": text}]}
    r = requests.post(url, headers=headers, json=data)
    if r.status_code != 200: print(f"⚠️ LINE 推播失敗: {r.status_code}")

# ==========================================
# 🎯 3. 核心多空 Webhook 智慧中轉監聽入口
# ==========================================
@app.route('/webhook', methods=['POST'])
def tradingview_webhook():
    # 🛡️ 雲端防護大絕招：force=True 強制解包，全面封殺 415 錯誤
    data = request.get_json(force=True, silent=True)
    if not data: return jsonify({"status": "error", "message": "無訊號內容"}), 400
    print("📥 雲端中轉站接收到新訊號:", data)

    # ❶ 處理 LINE 聊天室互動指令
    events = data.get('events', [])
    for event in events:
        if event.get('type') == 'message' and event['message'].get('type') == 'text':
            user_id = event['source'].get('userId')
            text = event['message'].get('text')
            reply_token = event.get('replyToken')
            
            if user_id == OWNER_USER_ID or text == "登入":
                is_allowed = verify_lifetime_user(user_id)
                if text == "登入":
                    if is_allowed:
                        reply_text = f"您的 ID：{user_id}\n✨ 帳號狀態：已成功開通【終身買斷版】權限，祝您交易順利！"
                    else:
                        reply_text = f"您的 ID：{user_id}\n⚠️ 帳號狀態：管理員未開通權限。\n\n請至戰情室網頁掃碼買斷，並提供此 ID 進行綁定。"
                    reply_message(reply_token, reply_text)
                else:
                    reply_message(reply_token, "戰情室後台已成功接收您的指令！")

    # ❷ 處理 TradingView 量化策略訊號
    is_tv_signal = 'action' in data and ('symbol' in data or 'code' in data)
    
    if is_tv_signal:
        action = data.get('action').lower()
        strategy_name = data.get('strategy', "量化策略")
        symbol = data.get('symbol', data.get('code', 'TXF1!'))
        try: price = float(data.get('price', 0))
        except: price = 0.0

        # 發射 A：即時手機 LINE 動態多空罐頭訊息
        if action == "buy":
            msg = f"策略:{strategy_name}\n📈【進場 - 多單】\n商品：{symbol}\n價格：{price}\n目標止盈：{price+180}\n防守止損：{price-120}"
            send_line_message(msg)
        elif action == "sell":
            msg = f"策略:{strategy_name}\n📉【進場 - 空單】\n商品：{symbol}\n價格：{price}\n目標止盈：{price-180}\n防守止損：{price+120}"
            send_line_message(msg)
        elif action == "exit":
            msg = f"策略:{strategy_name}\n🔚【全數平倉】\n商品：{symbol}\n平倉價：{price}"
            send_line_message(msg)

        # 發射 B：同步寫入 GitHub 雲端 market_status.json 戰情數據庫
        url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
        gh_headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        
        repo_resp = requests.get(url, headers=gh_headers)
        if repo_resp.status_code == 200:
            file_data = repo_resp.json()
            sha = file_data["sha"]
            
            # 安全解碼
            raw_content = base64.b64decode(file_data["content"]).decode('utf-8')
            current_content = json.loads(raw_content)
            
            if "strategy_positions" not in current_content:
                current_content["strategy_positions"] = []
                
            tw_tz = pytz.timezone('Asia/Taipei')
            now_str = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')
            
            # 🎯 核心邏輯：多空雙向部位智慧生成
            if action in ["buy", "sell"]:
                if action == "buy":
                    direction_label = "做多 📈"
                    tp_price = price + 180.0
                    sl_price = price - 120.0
                else: # action == "sell" 放空
                    direction_label = "做空 📉"
                    tp_price = price - 180.0  # 空單止盈在下方
                    sl_price = price + 120.0  # 空單止損在上方

                new_pos = {
                    "code": symbol,  # 透過與策略名稱結合的唯一識別代碼（防重複踩死）
                    "name": f"{strategy_name} ({direction_label})",
                    "buy_price": price,
                    "buy_time": now_str,
                    "pnl_percent": 0.0,
                    "tp_price": round(tp_price, 2),
                    "sl_price": round(sl_price, 2),
                    "is_closed": False,
                    "direction": action  # 供前端網頁 Vue 3 自動渲染霓虹變色
                }
                # 洗洗睡：只清除代碼完全相同的舊部位，確保多策略和平並存
                current_content["strategy_positions"] = [p for p in current_content["strategy_positions"] if p["code"] != symbol]
                current_content["strategy_positions"].append(new_pos)
                
            elif action == "exit":
                # 智慧結算多空盈虧
                for p in current_content["strategy_positions"]:
                    if p["code"] == symbol and not p["is_closed"]:
                        p["is_closed"] = True
                        p["close_price"] = price
                        p["close_time"] = now_str
                        
                        # 依多空方向智慧切換計算公式
                        if p.get("direction", "buy") == "buy":
                            p["pnl_percent"] = round(((price - p["buy_price"]) / p["buy_price"]) * 100, 2)
                        else: # 空單結算
                            p["pnl_percent"] = round(((p["buy_price"] - price) / p["buy_price"]) * 100, 2)

            # 強制轉化為純雙引號、無非典型字元的標準 JSON 字串
            updated_json_str = json.dumps(current_content, indent=4, ensure_ascii=False)
            updated_base64 = base64.b64encode(updated_json_str.encode('utf-8')).decode('utf-8')
            
            put_data = {"message": f"🤖 戰情室訊號同步更新 [{strategy_name} - {action}]", "content": updated_base64, "sha": sha}
            requests.put(url, headers=gh_headers, json=put_data)
            print(f"🚀 [雲端同步成功] {strategy_name} 數據已強制寫入 GitHub 全球戰情中心！")

    return jsonify({"status": "ok"}), 200

# ==========================================
# 🌐 4. 自動適應 Render 雲端運行環境
# ==========================================
if __name__ == '__main__':
    # 🎯 雲端部署核心防線：動態抓取平台隨機分配的 Port，抓不到才預設 5000
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 姜太雲端戰情室中轉站已就位，正運行於 Port: {port}")
    # ⚠️ 雲端部署 host 必須為 "0.0.0.0" 才能接受外網 TV 訊號傳入
    app.run(host="0.0.0.0", port=port, debug=False)
