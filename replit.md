# OCR 收支辨識系統 - 專案文件

## 專案概述
企業級 PyQt5 桌面應用程式，用於從 Google 相簿中選擇手寫帳單照片，透過雙引擎 OCR (Google Cloud Vision API + Tesseract) 進行文字辨識，並將結構化資料存入 Google 試算表。

**版本**: 1.0.0  
**建立日期**: 2025-10-16  
**技術棧**: Python 3.11, PyQt5, Google APIs, Tesseract OCR

## 最近變更
- 2025-10-16: 初始化專案結構
- 2025-10-16: 建立基礎 GUI 架構 (主視窗、圖片檢視器、資料編輯器)
- 2025-10-16: 實作 OAuth 2.0 認證模組 (Keyring 加密存儲)
- 2025-10-16: 配置 YAML 設定檔與日誌系統

## 專案架構

### 核心模組
- **main.py**: 應用程式進入點
- **src/auth/**: Google OAuth 2.0 認證管理
- **src/gui/**: PyQt5 GUI 元件
  - main_window.py: 主視窗 (分割視圖)
  - image_viewer.py: 圖片檢視器 (縮放、旋轉、ROI)
  - data_editor.py: 資料編輯面板
  - photo_selector.py: 相簿照片選擇器
- **src/ocr/**: OCR 引擎模組 (待實作)
- **src/api/**: Google APIs 整合 (待實作)
- **src/cache/**: 快取管理系統 (待實作)
- **src/processing/**: 批次處理與工作隊列 (待實作)
- **src/export/**: 資料匯出模組 (待實作)
- **src/utils/**: 工具函數 (logger, config)

### 配置檔案
- **config/settings.yaml**: 主要應用程式設定
- **config/client_secrets.json**: Google OAuth 憑證 (需自行設置)

### 資料目錄
- **data/cache/**: 圖片與縮圖快取
- **data/logs/**: 應用程式日誌
- **data/processed_photos/**: 已處理照片記錄
- **data/dictionaries/**: 自訂 OCR 字典

## 技術特色

### 1. OAuth 2.0 安全認證
- Authorization Code flow (桌面應用)
- python-keyring 加密 Token 存儲
- 自動 Token 刷新機制
- 最小權限範圍 (photoslibrary.readonly, spreadsheets)

### 2. 雙引擎 OCR 系統
- **Google Cloud Vision API**: 高精度手寫辨識
- **Tesseract OCR**: 本地備援引擎
- **Weighted Dempster-Shafer 融合**: 信心加權算法

### 3. 智能資料處理
- 多層後處理 (語言校正、貨幣標準化)
- 正則驗證 (日期、金額格式)
- 異常檢測 (總額不符、稅率驗證)

### 4. 批次處理架構
- concurrent.futures 工作池
- SQLite 持久化隊列
- Tenacity 重試策略 (指數退避 + jitter)
- 離線續傳支援

### 5. API 配額管理
- Token Bucket 速率限制
- 軟上限自動切換 (80% 配額 → Tesseract)
- 實時使用監控

### 6. 使用者體驗
- 分割視圖: 左側圖片、右側資料
- 圖片操作: 縮放、平移、旋轉、放大鏡
- ROI 手動框選
- 完整鍵盤快捷鍵支援
- 可調式 UI 布局 (持久化)

## 開發狀態

### 已完成 ✅
- [x] 專案結構建立 (模組化架構)
- [x] Python 環境與依賴安裝 (100+ 套件)
- [x] 配置系統 (YAML + Config 管理)
- [x] 日誌系統 (Rotating File Handler)
- [x] OAuth 2.0 認證模組 (Keyring + 檔案備援)
- [x] 主視窗 GUI (分割視圖)
- [x] 圖片檢視器 (縮放、平移、旋轉)
- [x] 資料編輯面板 (表格顯示)
- [x] ROI 選取工具 (矩形選擇)
- [x] Google Photos API 整合 (懶載入、分頁)
- [x] Google Sheets API 整合 (資料匯出)
- [x] Google Cloud Vision OCR (DOCUMENT_TEXT_DETECTION)
- [x] Tesseract OCR (影像前處理、扭曲校正)
- [x] 加權機率融合算法 (相似度驅動信心度調整)
- [x] 資料萃取器 (日期、項目、金額、總額分離)
- [x] 資料驗證器 (總額不符、稅率異常檢測)
- [x] 快取管理 (Disk Cache with TTL)
- [x] OCR 協調器 (完整處理管線)
- [x] 已處理照片追蹤系統 (防重複處理)
- [x] VNC 工作流程配置 (遠端桌面顯示)

### 開發中 🚧
- [ ] GUI 整合 (連接後端 OCR 與前端介面)
- [ ] 批次處理系統 (工作池、重試邏輯)
- [ ] API 配額監控與速率限制
- [ ] 照片選擇器 UI 完善

### 待規劃 📋
- [ ] 放大鏡工具實作
- [ ] 自訂字典學習功能
- [ ] NLP 語意驗證
- [ ] 完整審計日誌系統
- [ ] 多格式匯出 (CSV/JSON/XML) 實作
- [ ] 排程自動同步功能

## 使用者偏好設定

### GUI 操作
- 偏好繁體中文介面
- 重視資料核對流程 (必須人工確認後才能存入試算表)
- 需要錯誤紀錄與手動重新辨識功能

### 技術偏好
- 使用 PyQt5 建構桌面 GUI
- 雲端優先 (直接串流 Google Photos，不下載本地)
- 雙引擎 OCR 確保精準度
- 企業級錯誤處理與審計

## 設置需求

### Google Cloud 憑證
1. 建立 Google Cloud 專案
2. 啟用 APIs:
   - Google Photos Library API
   - Google Sheets API
   - Google Cloud Vision API
3. 建立 OAuth 2.0 憑證 (桌面應用程式)
4. 下載 `client_secrets.json` → `config/client_secrets.json`

### 環境變數 (可選)
- `GOOGLE_APPLICATION_CREDENTIALS`: Vision API 服務帳號金鑰路徑

## 執行方式

### 桌面模式 (本地)
```bash
python main.py
```

### VNC 模式 (Replit)
透過 VNC 工作流程執行，顯示桌面 GUI 介面。

## 注意事項
- 所有 OAuth Token 使用 keyring 加密存儲
- client_secrets.json 不應提交至版本控制
- 快取資料與日誌會自動清理
- API 配額接近上限時自動降速
