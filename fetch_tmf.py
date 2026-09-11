import pandas as pd
import requests
import zipfile
import io
import time
import os
import subprocess
from datetime import datetime, timedelta

# ==========================================
# 1. 設定工作目錄與抓取參數
# ==========================================
# 取得目前 Python 檔案所在的資料夾路徑 (即 tmf-data-api 資料夾)
current_dir = os.getcwd() 

# 設定抓取範圍 (以您指定的日期為例)
start_date = datetime(2026, 9, 7)
end_date = datetime(2026, 9, 10)
symbol = 'TMF'

all_data = []
current_date = start_date

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print("\n🚀 開始從期交所下載微台指資料...")

# ==========================================
# 2. 迴圈自動抓取每天的逐筆交易資料
# ==========================================
while current_date <= end_date:
    date_str = current_date.strftime('%Y_%m_%d')
    url = f"https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Daily_{date_str}.zip"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                csv_name = z.namelist()[0]
                with z.open(csv_name) as f:
                    df_day = pd.read_csv(f, encoding='big5', dtype=str)
                    df_day.columns = [col.strip() for col in df_day.columns]
                    df_day['商品代號'] = df_day['商品代號'].str.strip()

                    df_tmf = df_day[df_day['商品代號'] == symbol].copy()

                    if not df_tmf.empty:
                        all_data.append(df_tmf)
                        print(f"✅ 成功取得 {date_str} 的微台指資料！")
        else:
            print(f"⏸️ {date_str} 無資料 (週末或無交易)。")
    except Exception as e:
         print(f"❌ {date_str} 抓取錯誤: {e}")

    current_date += timedelta(days=1)
    time.sleep(1)

# ==========================================
# 3. 資料清洗、轉換 1分K 並存檔
# ==========================================
if len(all_data) > 0:
    print("\n⏳ 正在轉換為 1分鐘 K線並存檔...")
    df = pd.concat(all_data, ignore_index=True)

    df['成交時間'] = df['成交時間'].str.zfill(6)
    df['datetime'] = pd.to_datetime(df['成交日期'] + df['成交時間'], format='%Y%m%d%H%M%S')
    df['成交價格'] = pd.to_numeric(df['成交價格'], errors='coerce')
    df['成交數量(B+S)'] = pd.to_numeric(df['成交數量(B+S)'], errors='coerce')

    main_contract = df['到期月份(週別)'].value_counts().idxmax()
    df = df[df['到期月份(週別)'] == main_contract]
    df.set_index('datetime', inplace=True)

    df_1min = df.resample('1min').agg({
        '成交價格': ['first', 'max', 'min', 'last'],
        '成交數量(B+S)': 'sum'
    }).dropna()
    df_1min.columns = ['開盤價', '最高價', '最低價', '收盤價', '成交量']

    # 存檔至本機 (Excel 與 JSON)
    excel_path = os.path.join(current_dir, '微冰不加4.xlsx')
    json_path = os.path.join(current_dir, '微冰不加4.json')

    df_1min.to_excel(excel_path)
    
    df_json = df_1min.reset_index() 
    df_json['datetime'] = df_json['datetime'].astype(str)
    df_json.to_json(json_path, force_ascii=False, orient='records', indent=4)
    print(f"🎉 檔案已成功更新至：{current_dir}")

    # ==========================================
    # 4. 自動推送到 GitHub (GitOps)
    # ==========================================
    print("\n🌐 準備將資料同步至 GitHub...")
    # 定義要執行的 git 指令
    commands = [
        ["git", "add", "."],
        ["git", "commit", "-m", f"Auto update TMF data: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        ["git", "push"]
    ]

    for cmd in commands:
        try:
            # 讓 Python 在背景執行終端機指令
            result = subprocess.run(cmd, cwd=current_dir, capture_output=True, text=True, check=True)
            print(f"執行成功: {' '.join(cmd)}")
        except subprocess.CalledProcessError as e:
            # 如果沒有檔案更動，commit 會報錯，這是正常的，忽略即可
            if "nothing to commit" in e.stdout or "nothing to commit" in e.stderr:
                print("ℹ️ 資料沒有變動，無須上傳。")
            else:
                print(f"⚠️ 執行 {' '.join(cmd)} 時發生錯誤：\n{e.stderr}")

    print("\n✨ 全部流程執行完畢！您可以去 GitHub 檢查最新檔案了。")

else:
    print("\n⚠️ 這段期間內沒有抓到任何微台指的資料。")