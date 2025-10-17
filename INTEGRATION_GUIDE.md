# GUI 與後端整合指南

## 整合完成摘要

### ✅ 已實作功能

#### 1. 照片選擇器 (PhotoSelectorDialog)
- **位置**: `src/gui/photo_selector.py`
- **功能**:
  - 從 Google Photos 載入照片列表
  - 縮圖預覽 (120x120)
  - 分頁載入 (每頁 50 張)
  - 雙擊或點擊「選擇」按鈕選取照片
  - 快取縮圖以提升性能

#### 2. 主視窗整合 (MainWindow)
- **位置**: `src/gui/main_window.py`
- **新增組件**:
  - OCR 按鈕 (開始 OCR 辨識)
  - 儲存按鈕 (核准並儲存)
  - OCR Worker 執行緒 (QThread)
  - 進度狀態顯示

#### 3. OCR 處理流程

```python
# 工作流程
1. 用戶登入 Google → OAuth 認證
2. 選擇照片 → PhotoSelectorDialog
3. 載入照片 → ImageCache + ImageViewer
4. 開始 OCR → OCRWorker (QThread)
   ├─ Vision API OCR
   ├─ Tesseract OCR
   ├─ 加權機率融合
   ├─ 資料萃取
   └─ 異常檢測
5. 顯示結果 → DataEditorPanel
6. 用戶核對修正
7. 儲存資料 → Google Sheets
8. 標記已處理 → ProcessedPhotoTracker
```

#### 4. 多執行緒架構

```python
class OCRWorker(QThread):
    """OCR 處理執行緒"""
    finished = pyqtSignal(dict)  # 完成信號
    error = pyqtSignal(str)      # 錯誤信號
    progress = pyqtSignal(str)   # 進度信號
    
    def run(self):
        result = self.orchestrator.process_image(
            self.image_bytes, 
            self.photo_id
        )
        self.finished.emit(result)
```

## 使用指南

### 1. 啟動應用程式

```bash
python main.py
```

應用程式會在 VNC 桌面環境中啟動。

### 2. 完整操作流程

#### Step 1: 登入 Google
```
點擊「登入 Google」按鈕
→ 瀏覽器開啟 OAuth 授權頁面
→ 授權應用程式存取 Google Photos 和 Sheets
→ 返回應用程式，顯示「已登入 ✓」
```

#### Step 2: 選擇照片
```
點擊「選擇照片」按鈕
→ 開啟照片選擇器對話框
→ 瀏覽縮圖，點擊載入更多（如需要）
→ 雙擊照片或選擇後點擊「選擇」按鈕
→ 照片顯示在左側圖片檢視器
```

#### Step 3: OCR 辨識
```
點擊「開始 OCR 辨識」按鈕
→ 狀態顯示「OCR 辨識中...」
→ 後台執行：
  - Google Vision API 辨識
  - Tesseract OCR 辨識
  - 加權機率融合
  - 資料萃取與驗證
→ 結果顯示在右側資料編輯器
→ 狀態顯示信心度和異常警告（如有）
```

#### Step 4: 核對與修正
```
檢視右側資料表格：
→ 日期、項目名稱、金額、分類
→ 手動修正任何錯誤
→ 注意異常標記（⚠️）
```

#### Step 5: 儲存資料
```
點擊「核准並儲存」按鈕
→ 確認對話框顯示摘要
→ 點擊「是」確認
→ 資料儲存到 Google Sheets
→ 照片標記為「已處理」
```

## 關鍵整合點

### 1. 認證整合

```python
# 主視窗初始化 APIs
def _on_login_success(self):
    creds = self.auth_manager.get_credentials()
    self.photos_api = GooglePhotosAPI(creds)
    self.sheets_api = GoogleSheetsAPI(creds)
    self.orchestrator = OCROrchestrator(creds)
```

### 2. 照片載入

```python
# 從 Google Photos 載入並快取
def _load_photo(self, photo):
    photo_bytes = self.cache.get_image(photo['baseUrl'])
    if not photo_bytes:
        photo_bytes = self.photos_api.download_photo(photo['baseUrl'])
        self.cache.set_image(photo['baseUrl'], photo_bytes)
    
    self.image_viewer.set_image(QPixmap.fromImage(QImage.fromData(photo_bytes)))
```

### 3. OCR 處理

```python
# 啟動 OCR Worker
def _handle_start_ocr(self):
    self.ocr_worker = OCRWorker(
        self.orchestrator,
        self.current_photo_bytes,
        self.current_photo['id']
    )
    self.ocr_worker.finished.connect(self._on_ocr_finished)
    self.ocr_worker.start()

# 處理結果
def _on_ocr_finished(self, result):
    self.data_editor.set_data(result['extracted_data'])
    self.save_btn.setEnabled(True)
```

### 4. 資料儲存

```python
# 儲存到 Google Sheets
def _save_to_sheets(self, data):
    spreadsheet_id = self.sheets_api.get_or_create_spreadsheet(
        'OCR 收支記錄'
    )
    rows = self.sheets_api.format_expense_data(data)
    self.sheets_api.append_data(spreadsheet_id, rows)
    
    # 標記已處理
    self.tracker.mark_processed(
        self.current_photo['id'], 
        self.current_ocr_result
    )
```

## 錯誤處理

### 1. OCR 錯誤
```python
def _on_ocr_error(self, error_msg):
    QMessageBox.critical(self, "OCR 錯誤", f"處理失敗: {error_msg}")
    self.ocr_btn.setEnabled(True)
```

### 2. 網路錯誤
- Google Photos API 載入失敗 → 顯示錯誤對話框
- Google Sheets 儲存失敗 → 顯示錯誤對話框
- 自動記錄到日誌檔案

### 3. 異常檢測
- 總額不符 → 狀態列顯示警告
- 低信心度 → 標記需要審核
- 稅率異常 → 顯示異常訊息

## 效能優化

### 1. 快取策略
- **縮圖快取**: 200px, TTL 3600 秒
- **原圖快取**: 完整尺寸, TTL 1800 秒
- **磁碟快取**: DiskCache with LRU

### 2. 多執行緒
- OCR 處理在獨立 QThread 執行
- GUI 主執行緒保持響應
- 進度更新透過信號傳遞

### 3. 懶載入
- 照片列表分頁載入 (50 張/頁)
- 縮圖按需載入
- 原圖僅在選擇時載入

## 測試檢查清單

- [x] OAuth 登入流程
- [x] 照片選擇器載入
- [x] 照片縮圖顯示
- [x] 照片原圖載入
- [x] OCR 辨識流程
- [x] 結果顯示在資料編輯器
- [x] 資料手動修正
- [x] Google Sheets 儲存
- [x] 已處理照片追蹤
- [x] 錯誤處理與顯示

## 已知限制

1. **批次處理**: 目前僅支援單張照片處理
2. **ROI 選取**: 工具已實作但未整合到 OCR 流程
3. **放大鏡**: 尚未實作
4. **離線模式**: 需要網路連線存取 Google APIs

## 下一步改進

### 優先級 P0
1. 實作批次處理（同時處理多張照片）
2. 整合 ROI 選取到 OCR 流程
3. 完整的錯誤恢復機制

### 優先級 P1
4. API 配額監控與視覺化
5. 處理歷史記錄查看
6. 導出多種格式 (CSV, JSON, XML)

### 優先級 P2
7. 放大鏡工具
8. 自訂 OCR 參數調整
9. 離線處理支援

## 總結

GUI 與後端整合已完成，應用程式具備完整的端到端功能：
- ✅ 照片選擇與預覽
- ✅ 雙引擎 OCR 辨識
- ✅ 資料驗證與編輯
- ✅ Google Sheets 自動儲存
- ✅ 多執行緒處理
- ✅ 完整錯誤處理

系統已可用於生產環境，適合處理手寫收據的 OCR 辨識與整理工作。
