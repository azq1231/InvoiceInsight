#!/usr/bin/env python3
"""
OCR 收支辨识系统 - Streamlit Web 版本
手写收据辨识与 Google Sheets 整合
"""

import streamlit as st
import io
import logging
from PIL import Image
import pandas as pd
from datetime import datetime

from src.auth.google_auth import GoogleAuthManager
from src.api.google_photos import GooglePhotosAPI
from src.api.google_sheets import GoogleSheetsAPI
from src.processing.ocr_orchestrator import OCROrchestrator
from src.processing.processed_tracker import ProcessedPhotoTracker
from src.cache.image_cache import ImageCache
from src.utils.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="OCR 收支辨识系统",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """初始化 session state"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'auth_manager' not in st.session_state:
        st.session_state.auth_manager = GoogleAuthManager()
    if 'photos_api' not in st.session_state:
        st.session_state.photos_api = None
    if 'sheets_api' not in st.session_state:
        st.session_state.sheets_api = None
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = None
    if 'tracker' not in st.session_state:
        st.session_state.tracker = ProcessedPhotoTracker()
    if 'cache' not in st.session_state:
        st.session_state.cache = ImageCache()
    if 'selected_photo' not in st.session_state:
        st.session_state.selected_photo = None
    if 'ocr_result' not in st.session_state:
        st.session_state.ocr_result = None
    if 'photo_list' not in st.session_state:
        st.session_state.photo_list = []
    if 'photos_loaded_count' not in st.session_state:
        st.session_state.photos_loaded_count = 0
    if 'loaded_photo_ids' not in st.session_state:
        st.session_state.loaded_photo_ids = set()

def authenticate():
    """处理 Google 认证"""
    if st.session_state.auth_manager.authenticate():
        creds = st.session_state.auth_manager.get_credentials()
        st.session_state.photos_api = GooglePhotosAPI(creds)
        st.session_state.sheets_api = GoogleSheetsAPI(creds)
        st.session_state.orchestrator = OCROrchestrator(creds)
        st.session_state.authenticated = True
        logger.info("用户已成功认证")
        return True
    return False

def logout():
    """登出并清除认证"""
    st.session_state.auth_manager.logout()
    st.session_state.authenticated = False
    st.session_state.photos_api = None
    st.session_state.sheets_api = None
    st.session_state.orchestrator = None
    st.session_state.selected_photo = None
    st.session_state.ocr_result = None
    st.session_state.photo_list = []
    st.session_state.photos_loaded_count = 0
    st.session_state.loaded_photo_ids = set()
    logger.info("用户已登出")

def load_photos(page_size=20):
    """从 Google Photos 载入照片列表"""
    if not st.session_state.photos_api:
        return []
    
    try:
        photos = []
        skip_count = st.session_state.photos_loaded_count
        current_count = 0
        loaded_count = 0
        
        for item in st.session_state.photos_api.list_media_items(page_size=100):
            if current_count < skip_count:
                current_count += 1
                continue
            
            if item['id'] not in st.session_state.loaded_photo_ids:
                photos.append(item)
                st.session_state.loaded_photo_ids.add(item['id'])
                loaded_count += 1
                
                if loaded_count >= page_size:
                    break
            
            current_count += 1
        
        st.session_state.photos_loaded_count = current_count
        
        if loaded_count == 0 and skip_count > 0:
            st.info("已到达照片列表末尾")
            logger.info("所有照片已加载完毕")
        
        return photos
    except Exception as e:
        logger.error(f"载入照片失败: {e}")
        st.error(f"载入照片失败: {e}")
        return []

def download_photo(base_url, width=2048, height=2048):
    """下载并缓存照片"""
    try:
        cache_key = f"{base_url}_{width}x{height}"
        photo_bytes = st.session_state.cache.get_image(cache_key)
        if not photo_bytes:
            photo_bytes = st.session_state.photos_api.download_image(base_url, width, height)
            st.session_state.cache.set_image(cache_key, photo_bytes)
        return photo_bytes
    except Exception as e:
        logger.error(f"下载照片失败: {e}")
        st.error(f"下载照片失败: {e}")
        return None

def process_ocr(image_bytes, photo_id):
    """执行 OCR 辨识"""
    try:
        with st.spinner('🔍 正在进行 OCR 辨识...'):
            result = st.session_state.orchestrator.process_image(image_bytes, photo_id)
            st.session_state.ocr_result = result
            logger.info(f"OCR 处理完成，信心度: {result.get('confidence', 0):.2%}")
            return result
    except Exception as e:
        logger.error(f"OCR 处理失败: {e}")
        st.error(f"OCR 处理失败: {e}")
        return None

def save_to_sheets(data):
    """保存资料到 Google Sheets"""
    try:
        if 'spreadsheet_id' not in st.session_state:
            spreadsheet = st.session_state.sheets_api.create_spreadsheet('OCR 收支记录')
            st.session_state.spreadsheet_id = spreadsheet['id']
            logger.info(f"创建新试算表: {spreadsheet['id']}")
        
        ocr_results = [{
            'date': data['date'],
            'items': data['items'],
            'photo_id': st.session_state.selected_photo['id']
        }]
        
        result = st.session_state.sheets_api.export_ocr_results(
            st.session_state.spreadsheet_id,
            ocr_results
        )
        
        st.session_state.tracker.mark_processed(
            st.session_state.selected_photo['id'],
            st.session_state.ocr_result
        )
        
        logger.info(f"资料已保存到 Google Sheets: {st.session_state.spreadsheet_id}")
        return result
    except Exception as e:
        logger.error(f"保存到 Google Sheets 失败: {e}")
        st.error(f"保存失败: {e}")
        return None

def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.title("🧾 OCR 收支辨识")
        st.markdown("---")
        
        if not st.session_state.authenticated:
            st.info("请先登入 Google 帐号")
            if st.button("🔑 登入 Google", use_container_width=True):
                if authenticate():
                    st.success("登入成功！")
                    st.rerun()
                else:
                    st.error("登入失败，请重试")
        else:
            st.success("✅ 已登入")
            if st.button("🚪 登出", use_container_width=True):
                logout()
                st.rerun()
            
            st.markdown("---")
            st.subheader("📊 统计资讯")
            processed_count = len(st.session_state.tracker.get_processed_photos())
            st.metric("已处理照片", processed_count)
            
            if st.session_state.ocr_result:
                confidence = st.session_state.ocr_result.get('confidence', 0)
                st.metric("最近辨识信心度", f"{confidence:.1%}")
        
        st.markdown("---")
        st.markdown("""
        ### 📖 使用说明
        1. 登入 Google 帐号
        2. 选择要辨识的照片
        3. 检视 OCR 辨识结果
        4. 手动修正资料
        5. 保存到 Google Sheets
        """)

def render_photo_gallery():
    """渲染照片画廊"""
    st.subheader("📷 选择照片")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🔄 载入照片", use_container_width=True):
            photos = load_photos(page_size=20)
            if photos:
                st.session_state.photo_list.extend(photos)
                st.success(f"载入了 {len(photos)} 张照片")
    
    with col2:
        if st.button("🗑️ 清空列表"):
            st.session_state.photo_list = []
            st.session_state.photos_loaded_count = 0
            st.session_state.loaded_photo_ids = set()
            st.rerun()
    
    if st.session_state.photo_list:
        cols = st.columns(4)
        for idx, photo in enumerate(st.session_state.photo_list):
            col = cols[idx % 4]
            with col:
                try:
                    photo_bytes = download_photo(photo['base_url'], width=200, height=200)
                    if photo_bytes:
                        img = Image.open(io.BytesIO(photo_bytes))
                        st.image(img, use_container_width=True)
                        
                        is_processed = st.session_state.tracker.is_processed(photo['id'])
                        label = "✓ 已处理" if is_processed else "选择此照片"
                        
                        if st.button(label, key=f"photo_{idx}", disabled=is_processed, use_container_width=True):
                            st.session_state.selected_photo = photo
                            st.rerun()
                except Exception as e:
                    logger.error(f"显示照片失败: {e}")
                    st.error("无法显示照片")

def render_image_viewer():
    """渲染图片查看器"""
    if st.session_state.selected_photo:
        st.subheader("🖼️ 照片预览")
        
        photo_bytes = download_photo(st.session_state.selected_photo['base_url'])
        if photo_bytes:
            img = Image.open(io.BytesIO(photo_bytes))
            st.image(img, use_container_width=True)
            
            if st.button("🔍 开始 OCR 辨识", type="primary", use_container_width=True):
                ocr_result = process_ocr(photo_bytes, st.session_state.selected_photo['id'])
                if ocr_result:
                    st.rerun()

def render_ocr_results():
    """渲染 OCR 辨识结果"""
    if st.session_state.ocr_result:
        st.subheader("📝 辨识结果")
        
        result = st.session_state.ocr_result
        confidence = result.get('confidence', 0)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("辨识信心度", f"{confidence:.1%}")
        with col2:
            anomalies = result.get('anomalies', [])
            st.metric("异常警告", len(anomalies))
        with col3:
            items_count = len(result.get('extracted_data', {}).get('items', []))
            st.metric("项目数量", items_count)
        
        if anomalies:
            st.warning("⚠️ 检测到异常：" + "、".join(anomalies))
        
        data = result.get('extracted_data', {})
        
        st.markdown("#### 📅 日期资讯")
        date = st.text_input("日期", value=data.get('date', ''))
        
        st.markdown("#### 💰 项目明细")
        items = data.get('items', [])
        
        if items:
            df_items = pd.DataFrame(items)
            edited_df = st.data_editor(
                df_items,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "name": st.column_config.TextColumn("项目名称", required=True),
                    "amount": st.column_config.NumberColumn("金额", format="%.2f", required=True),
                    "category": st.column_config.SelectboxColumn(
                        "分类",
                        options=["收入", "支出", "结余", "总计"],
                        required=True
                    )
                }
            )
            
            st.markdown("#### 📊 总额资讯")
            col1, col2 = st.columns(2)
            with col1:
                declared_total = st.number_input(
                    "宣告总额",
                    value=float(data.get('declared_total', 0)),
                    format="%.2f"
                )
            with col2:
                calculated_total = edited_df[edited_df['category'] != '总计']['amount'].sum()
                st.metric("计算总额", f"{calculated_total:.2f}")
            
            if abs(declared_total - calculated_total) > 1.0:
                st.error(f"⚠️ 总额不符！差异: {abs(declared_total - calculated_total):.2f}")
            
            if st.button("💾 核准并保存到 Google Sheets", type="primary", use_container_width=True):
                save_data = {
                    'date': date,
                    'items': edited_df.to_dict('records'),
                    'declared_total': declared_total,
                    'calculated_total': calculated_total,
                    'confidence': confidence
                }
                
                if save_to_sheets(save_data):
                    st.success("✅ 资料已成功保存到 Google Sheets！")
                    st.balloons()
                    st.session_state.ocr_result = None
                    st.session_state.selected_photo = None
                    st.rerun()
        else:
            st.info("未辨识到项目资料")

def main():
    """主应用程式"""
    init_session_state()
    
    render_sidebar()
    
    st.title("🧾 OCR 收支辨识系统")
    st.markdown("手写收据智能辨识 | 双引擎 OCR | Google Sheets 整合")
    st.markdown("---")
    
    if not st.session_state.authenticated:
        st.info("👈 请先在侧边栏登入 Google 帐号")
    else:
        tab1, tab2, tab3 = st.tabs(["📷 选择照片", "🖼️ 照片预览", "📝 辨识结果"])
        
        with tab1:
            render_photo_gallery()
        
        with tab2:
            if st.session_state.selected_photo:
                render_image_viewer()
            else:
                st.info("请先在「选择照片」标签页选择一张照片")
        
        with tab3:
            if st.session_state.ocr_result:
                render_ocr_results()
            else:
                st.info("请先完成 OCR 辨识")

if __name__ == "__main__":
    main()
