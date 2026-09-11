import os
import shutil
import subprocess
import pandas as pd
import requests
import zipfile
import io
from datetime import datetime, timedelta

# ==========================================
# 1. 日期設定：自動抓取當天與過去 7 天
# ==========================================
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

print("🚀 開始從期交所下載微台指資料...")
all_data = []
current_date = start_date

# ==========================================
# 2. 爬取與處理期交所資料
# ==========================================
while current_date <= end_date:
    date_str = current_date.strftime("%Y_%m_%d")
    url = f"https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Daily_{date_str}.zip"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                csv_filename = z.namelist()[0]
                with z.open(csv_filename) as f:
                    df = pd.read_csv(f, encoding='big5', dtype=str)
                    
                    # 清理欄位與過濾微台指 (TMF)
                    df.columns = [col.strip() for col in df.columns]
                    df['商品代號'] = df['商品代號'].str.strip()
                    df_tmf = df[df['商品代號'] == 'TMF'].copy()
                    
                    if not df_tmf.empty:
                        # 自動鎖定主力合約
                        df_tmf['到期月份(週別)'] = df_tmf['到期月份(週別)'].str.strip()
                        main_month = df_tmf['到期月份(週別)'].value_counts().idxmax()
                        
                        df_tmf_main = df_tmf[df_tmf['到期月份(週別)'] == main_month].copy()
                        all_data.append(df_tmf_main)
                        print(f"✅ 成功取得 {date_str} 微台指資料！(自動鎖定主力合約: {main_month})")
    except Exception:
        pass # 遇到假日或無資料則略過
        
    current_date += timedelta(days=1)

print("⏳ 正在轉換為 1分鐘 K線並存檔...")

if all_data:
    df_all = pd.concat(all_data, ignore_index=True)
    
    # ==========================================
    # 3. 整理為 1 分鐘 K 線 (開高低收量)
    # ==========================================
    df_all['成交日期'] = df_all['成交日期'].str.strip()
    df_all['成交時間'] = df_all['成交時間'].astype(str).str.zfill(6)
    df_all['datetime'] = pd.to_datetime(df_all['成交日期'] + ' ' + df_all['成交時間'], format='%Y%m%d %H%M%S')
    
    # 兩萬點防禦過濾
    df_all['成交價格'] = pd.to_numeric(df_all['成交價格'], errors='coerce')
    df_all = df_all[df_all['成交價格'] > 20000]
    
    df_all['成交數量(B+S)'] = pd.to_numeric(df_all['成交數量(B+S)'], errors='coerce') // 2
    
    df_all.set_index('datetime', inplace=True)
    df_1min = df_all.resample('1min').agg({
        '成交價格': ['first', 'max', 'min', 'last'],
        '成交數量(B+S)': 'sum'
    }).dropna()
    
    df_1min.columns = ['開盤價', '最高價', '最低價', '收盤價', '成交量']
    df_1min.reset_index(inplace=True)
    df_1min['datetime'] = df_1min['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # ==========================================
    # 4. 存檔至本機 Mac 專案資料夾
    # ==========================================
    current_dir = os.getcwd()
    excel_path = os.path.join(current_dir, '微冰不加4.xlsx')
    json_path = os.path.join(current_dir, '微冰不加4.json')
    
    df_1min.to_excel(excel_path, index=False)
    df_1min.to_json(json_path, orient='records', force_ascii=False)
    print(f"🎉 檔案已成功更新至：{current_dir}")

    # ==========================================
    # 5. 雙重備份至 Google Drive (kTra 資料夾)
    # ==========================================
    drive_folder = '/Users/pingchunkao/Library/CloudStorage/GoogleDrive-clarkmurk@gmail.com/我的雲端硬碟/kTra'
    
    try:
        excel_dest = f"{drive_folder}/微冰不加4.xlsx"
        json_dest = f"{drive_folder}/微冰不加4.json"
        
        # 🌟 破解 macOS 雲端死結：如果舊檔案存在，先把它刪除！
        if os.path.exists(excel_dest):
            os.remove(excel_dest)
        if os.path.exists(json_dest):
            os.remove(json_dest)
            
        shutil.copy('微冰不加4.xlsx', excel_dest)
        shutil.copy('微冰不加4.json', json_dest)
        print("📁 雙重備份成功！檔案已同步放入 Google Drive 的 kTra 資料夾。")
    except Exception as e:
        print(f"⚠️ Google Drive 備份失敗，請檢查路徑: {e}")

    # ==========================================
    # 6. 準備將資料同步至 GitHub
    # ==========================================
    print("🌐 準備將資料同步至 GitHub...")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    try:
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', f'Auto update TMF data: {current_time}'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print("✨ 全部流程執行完畢！您可以去 GitHub 檢查最新檔案了。")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ 執行 Git 指令時發生錯誤 (若顯示 nothing to commit 代表無變更): {e}")
else:
    print("⚠️ 過去 7 天內沒有找到任何微台指資料。")