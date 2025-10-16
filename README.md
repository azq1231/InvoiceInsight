# OCR 收支辨識系統

企業級手寫帳單自動辨識與整理工具，使用 Google Cloud Vision API 與 Tesseract OCR 進行雙引擎文字辨識。

## 功能特色

### 核心功能
- **雙引擎 OCR**: Google Cloud Vision API + Tesseract
- **加權融合算法**: Weighted Dempster-Shafer (W-DST) 信心融合
- **智能驗證**: 多層後處理、正則驗證、異常檢測
- **批次處理**: 併發工作池、持久化隊列、離線續傳
- **配額管理**: Token Bucket 演算法、自動降速、備援策略

### 使用者介面
- **分割視圖**: 左側圖片檢視器、右側資料編輯面板
- **圖片操作**: 縮放、平移、旋轉、放大鏡工具
- **ROI 選取**: 手動框選辨識區域
- **鍵盤快捷鍵**: 快速操作與導航
- **可調式布局**: 面板位置、縮放比例可持久化

### 安全與認證
- **OAuth 2.0**: Authorization Code flow
- **Keyring 加密**: 安全的 Token 存儲
- **自動刷新**: Token 到期前自動更新
- **最小權限**: photoslibrary.readonly, spreadsheets

## 安裝設置

### 前置需求
- Python 3.11+
- Tesseract OCR
- Google Cloud Vision API 憑證
- Google OAuth 2.0 憑證

### 安裝步驟

1. 安裝依賴套件（已自動安裝）

2. 設置 Google OAuth 憑證
   - 前往 [Google Cloud Console](https://console.cloud.google.com/)
   - 創建 OAuth 2.0 憑證（桌面應用程式類型）
   - 下載 `client_secrets.json` 並放置於 `config/` 目錄

3. 設置 Google Cloud Vision API
   - 在 Google Cloud Console 啟用 Vision API
   - 創建 API 密鑰或服務帳號

4. 配置應用程式
   - 編輯 `config/settings.yaml` 調整設定

## 使用方式

### 啟動應用程式

```bash
python main.py
```

### 操作流程

1. **登入 Google 帳號**: 點擊「登入 Google」按鈕
2. **選擇照片**: 從 Google 相簿選擇要辨識的照片
3. **框選區域**: (可選) 手動框選要辨識的區域
4. **執行 OCR**: 點擊「開始 OCR 辨識」
5. **核對資料**: 檢查右側辨識結果，手動修正錯誤
6. **核准儲存**: 確認無誤後點擊「核准並儲存」

### 鍵盤快捷鍵

- **Ctrl+P**: 選擇照片
- **Ctrl+O**: 開始 OCR 辨識
- **Ctrl++**: 放大圖片
- **Ctrl+-**: 縮小圖片
- **Ctrl+R**: 順時針旋轉
- **Ctrl+Shift+R**: 逆時針旋轉
- **Ctrl+S**: ROI 選取
- **Ctrl+A**: 核准資料
- **Ctrl+X**: 拒絕資料
- **Ctrl+J**: 跳至異常項目
- **Left/Right**: 上一張/下一張照片

## 專案結構

```
.
├── main.py                 # 應用程式進入點
├── config/                 # 配置檔案
│   ├── settings.yaml       # 主要設定
│   └── client_secrets.json # OAuth 憑證
├── src/
│   ├── auth/              # 認證模組
│   ├── gui/               # GUI 元件
│   ├── ocr/               # OCR 引擎
│   ├── api/               # API 整合
│   ├── cache/             # 快取管理
│   ├── processing/        # 批次處理
│   ├── export/            # 資料匯出
│   └── utils/             # 工具函數
├── data/
│   ├── cache/             # 圖片快取
│   ├── logs/              # 日誌檔案
│   ├── processed_photos/  # 處理記錄
│   └── dictionaries/      # 自訂字典
└── tests/                 # 測試檔案

## 技術架構

### OCR 引擎
- **Google Cloud Vision API**: 高精度雲端 OCR
- **Tesseract**: 本地備援 OCR
- **W-DST 融合**: 加權信心融合算法

### 資料處理
- **多層後處理**: 語言校正、貨幣標準化、全/半形轉換
- **正則驗證**: 日期、金額、稅率格式檢查
- **異常檢測**: 總額不符、稅率異常、低信心標註

### 批次處理
- **併發控制**: concurrent.futures 工作池
- **持久化隊列**: SQLite + persist-queue
- **重試策略**: Tenacity + 指數退避

### 配額管理
- **Token Bucket**: 速率限制演算法
- **軟上限檢測**: 80% 配額自動切換 Tesseract
- **使用監控**: 實時追蹤 API 配額

## 授權

此專案為內部使用工具，所有權歸屬於專案建立者。
```
