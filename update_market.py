import yfinance as yf
import json
import os
import requests
from datetime import datetime
import pytz

def fetch_market_and_chips():
    print("🚀 姜太戰情室高頻機器人：啟動全球大盤數據更新...")
    tw_tz = pytz.timezone('Asia/Taipei')
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. 抓取全球美股與台股大盤最穩健的指標
    tickers = {
        "taiex": "^TWII",    # 台股加權指數
        "nasdaq": "^IXIC",   # 那斯達克指數
        "tsm_adr": "TSM",    # 台積電 ADR
        "sox": "^SOX",       # 費城半導體
        "dji": "^DJI"        # 道瓊工業
    }
    market_index_result = {}
    
    for key, ticker_symbol in tickers.items():
        try:
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(period='2d')
            if not df.empty and len(df) >= 2:
                price = round(df['Close'].iloc[-1], 2)
                change = round(df['Close'].iloc[-1] - df['Close'].iloc[-2], 2)
                percent = round((change / df['Close'].iloc[-2]) * 100, 2)
            else:
                price = round(df['Close'].iloc[-1], 2) if not df.empty else 0.0
                change, percent = 0.0, 0.0
            market_index_result[key] = {"price": price, "change": change, "percent": percent}
        except Exception as e:
            print(f"⚠️ {key} 數據抓取微幅異常: {e}")
            market_index_result[key] = {"price": 0.0, "change": 0.0, "percent": 0.0}

    # 欄位安全結構對接：維持台指期日盤(tx)的格式相容性
    market_index_result["tx"] = market_index_result["taiex"]

    # 2. 籌碼資料安全框架 (保留與歷史前端相容)
    chips_result = {
        "foreign_futures_net": -25600, 
        "retail_ratio": 12.5,
        "institutional_buying": { "foreign": -120.5, "itc": 45.2, "dealer": -12.3 }
    }

    # 3. 🛡️ 超級重點：讀取舊 JSON，實施 TradingView 持倉數據保護防線
    json_path = 'market_status.json'
    saved_positions = [] # 用來安全暫存 TradingView 傳進來的真單
    
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
                # 🛡️ 關鍵防線：如果舊檔案裡已經有 TV 寫入的單子，立刻把它們複製出來保護！
                if "strategy_positions" in existing_data and isinstance(existing_data["strategy_positions"], list):
                    saved_positions = existing_data["strategy_positions"]
                    print(f"🛡️ 國防級守護：成功保護現有的 {len(saved_positions)} 筆 TradingView 真實策略單！")
            except Exception as e:
                print(f"💡 提示：讀取舊 JSON 失敗或格式為空，將重新初始化結構。原因: {e}")

    # 4. 組裝全新封包
    final_output = {
        "last_update": current_time,
        "market_index": market_index_result,
        "chips": chips_result,
        # 🎯 完美的資料對接：把受保護的真實持倉單（或空陣列）原封不動塞回去，絕不覆蓋洗掉！
        "strategy_positions": saved_positions 
    }

    # 5. 寫入回檔案
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)
    print(f"🎉 戰情室大盤數據同步完成！更新時間：{current_time}")

if __name__ == '__main__':
    fetch_market_and_chips()
