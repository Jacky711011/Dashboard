import yfinance as yf
import json
import os
from datetime import datetime
import pytz

def fetch_market_data():
    print("🚀 姜太自動化機器人啟動：正在撈取全球市場數據...")
    
    # 設定台灣時間戳記
    tw_tz = pytz.timezone('Asia/Taipei')
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')
    
    # 定義 yfinance 爬取目標 (加權指數, 台指期近月, 那斯達克)
    tickers = {
        "taiex": "^TWII",
        "tx": "WTX=F",
        "nasdaq": "^IXIC"
    }
    
    market_index_result = {}
    
    for key, ticker_symbol in tickers.items():
        try:
            print(f"正在抓取 {key} ({ticker_symbol}) ...")
            ticker = yf.Ticker(ticker_symbol)
            # 抓取最近 2 天的數據以計算漲跌
            df = ticker.history(period='2d')
            
            if len(df) >= 2:
                close_today = df['Close'].iloc[-1]
                close_yesterday = df['Close'].iloc[-2]
                
                change = round(close_today - close_yesterday, 2)
                percent = round((change / close_yesterday) * 100, 2)
                price = round(close_today, 2)
                
                market_index_result[key] = {
                    "price": price,
                    "change": change,
                    "percent": percent
                }
                print(f"➔ {key} 成功！最新價: {price}, 漲跌: {change} ({percent}%)")
            elif len(df) == 1:
                # 萬一剛好遇到開盤第一筆或歷史數據不足
                price = round(df['Close'].iloc[-1], 2)
                market_index_result[key] = {
                    "price": price,
                    "change": 0.0,
                    "percent": 0.0
                }
                print(f"➔ {key} 成功(數據不足1日)！最新價: {price}")
            else:
                raise Exception("yfinance 回傳空數據")
                
        except Exception as e:
            print(f"❌ 抓取 {key} 失敗: {e}")
            # 萬一失敗，給予預設安全數值，避免網頁整張掛掉
            market_index_result[key] = { "price": 0.0, "change": 0.0, "percent": 0.0 }

    # 讀取現有的 JSON（保留籌碼與選股），只更新大盤數據與時間
    json_path = 'market_status.json'
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except:
                existing_data = {}
    else:
        existing_data = {}

    # 更新或初始化 JSON 結構
    existing_data["last_update"] = current_time
    existing_data["market_index"] = market_index_result
    
    # 確保 chips 與 strategy_picks 結構存在（若原先沒有就建立空的）
    if "chips" not in existing_data:
        existing_data["chips"] = {
            "foreign_futures_net": 0,
            "retail_ratio": 0.0,
            "institutional_buying": { "foreign": 0.0, "itc": 0.0, "dealer": 0.0 }
        }
    if "strategy_picks" not in existing_data:
        existing_data["strategy_picks"] = []

    # 寫回 JSON 檔案
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)
        
    print(f"🎉 戰情室 JSON 檔案更新成功！時間：{current_time}")

if __name__ == '__main__':
    fetch_market_data()
