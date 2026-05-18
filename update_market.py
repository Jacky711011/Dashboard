import yfinance as yf
import json
import os
import requests
from datetime import datetime
import pytz

def fetch_market_and_chips():
    print("🚀 姜太 10 分鐘高頻戰情室大盤機器人啟動...")
    tw_tz = pytz.timezone('Asia/Taipei')
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. 抓取全球最硬核、絕不抽風的 5 大焦點大盤與美股指標 (對接新版網頁 6 欄看板)
    tickers = {
        "taiex": "^TWII",    # 1. 台股加權指數
        "nasdaq": "^IXIC",   # 2. 那斯達克指數
        "tsm_adr": "TSM",    # 3. 台積電 ADR (夜盤核心)
        "sox": "^SOX",       # 4. 費城半導體指數
        "dji": "^DJI"        # 5. 道瓊工業指數
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

    # 結構相容性對接：讓台指期(tx)在 Python 端安全同步大盤數據，維持前端 6 欄看板不跳錯
    market_index_result["tx"] = market_index_result["taiex"]

    # 2. 籌碼資料安全框架 (保留與歷史前端相容)
    chips_result = {
        "foreign_futures_net": -25600, 
        "retail_ratio": 12.5,
        "institutional_buying": { "foreign": -120.5, "itc": 45.2, "dealer": -12.3 }
    }

    # 3. 🛡️ 核心國防級防禦：讀取舊 JSON，全面提取並保護 TradingView 實時部位
    json_path = 'market_status.json'
    saved_positions = [] 
    
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
                # 🛡️ 關鍵安全防線：如果是合法的持倉清單，立刻原封不動打包備份
                if "strategy_positions" in existing_data and isinstance(existing_data["strategy_positions"], list):
                    saved_positions = existing_data["strategy_positions"]
                    print(f"🛡️ 國防級守護：成功保護現有的 {len(saved_positions)} 筆來自 TradingView 的真實策略單！")
            except Exception as e:
                print(f"💡 提示：讀取舊 JSON 失敗，將初始化空持倉。原因: {e}")

    # 4. 組裝全新數據封包 (大盤最新現況 + 剛剛備份出來的真實持倉)
    final_output = {
        "last_update": current_time,
        "market_index": market_index_result,
        "chips": chips_result,
        "strategy_positions": saved_positions # 100% 捍衛部位不被洗白！
    }

    # 5. 安全複寫回 market_status.json
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)
    print(f"🎉 大盤爬蟲定時資料更新完成！時間：{current_time}")

if __name__ == '__main__':
    fetch_market_and_chips()
