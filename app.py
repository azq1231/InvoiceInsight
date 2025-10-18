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
        # 修复 redirect_uri_mismatch 错误
        # 在初始化时就传入固定的回调地址
        redirect_uri = "http://localhost:8501"
        st.session_state.auth_manager = GoogleAuthManager(redirect_uri=redirect_uri)
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
    if 'oauth_flow' not in st.session_state:
        st.session_state.oauth_flow = None

def authenticate():
    """处理 Google 认证"""
    # 此函数应在凭证获取后调用，以初始化所有 API 服务
    try:
        creds = st.session_state.auth_manager.get_credentials()
        if not creds:
            logger.warning("authenticate() 被调用，但没有可用的凭证")
            return False

        st.session_state.photos_api = GooglePhotosAPI(creds)
        st.session_state.sheets_api = GoogleSheetsAPI(creds)
        st.session_state.orchestrator = OCROrchestrator(creds)
        st.session_state.authenticated = True
        logger.info("用户已成功认证")
        return True
    except Exception as e:
        logger.error(f"认证失败: {e}")
        st.error(f"初始化 API 服务失败: {e}")
        return False

def logout():
    """登出并清除认证"""
    if 'auth_manager' in st.session_state:
        st.session_state.auth_manager.logout()
    
    # 迭代并清除所有 session state 键，以确保完全重置
    for key in list(st.session_state.keys()):
        del st.session_state[key]
        
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
            st.info("请登入 Google 以使用完整功能")

            if st.button("🔗 开始 Google 授权", use_container_width=True):
                result = st.session_state.auth_manager.get_auth_url()
                if result:
                    auth_url, state, flow = result
                    st.session_state.oauth_url = auth_url
                    st.session_state.oauth_state = state
                    st.session_state.oauth_flow = flow # 保存 flow 对象
                else:
                    st.session_state.oauth_url = False # Mark as failed to prevent re-rendering link
                    st.error("❌ 无法生成授权 URL。请检查 `client_secrets.json` 配置和网络连接。")

            if st.session_state.get('oauth_url'):
                st.markdown(f'**步骤 1:** <a href="{st.session_state.oauth_url}" target="_blank" rel="noopener noreferrer">点击这里打开 Google 授权页面</a>', unsafe_allow_html=True)
                st.markdown("**步骤 2:** 授权后，从浏览器地址栏复制授权码。")
                st.info("💡 提示：授权码在 `code=` 和 `&` 之间。")
                st.info("授权成功后，此页面将自动刷新。")
        else:
            st.success("✅ 已登入")
            if st.button("🚪 登出", use_container_width=True):
                logout()
                st.rerun()
            
            st.markdown("---")
            st.subheader("📊 统计资讯")
            processed_count = st.session_state.tracker.get_processed_count()
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
            
            # 只在已登入时显示保存按钮
            if st.session_state.authenticated and st.session_state.sheets_api:
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
                st.info("💡 提示：登入 Google 帐号后即可保存到 Google Sheets")
        else:
            st.info("未辨识到项目资料")

def render_upload_tab():
    """渲染上传照片标签页"""
    st.subheader("📤 上传照片进行辨识")
    st.markdown("支持 JPG、PNG、JPEG 格式的照片")
    
    uploaded_file = st.file_uploader(
        "选择要辨识的照片",
        type=["jpg", "jpeg", "png"],
        help="上传手写收据或帐单的照片"
    )
    
    if uploaded_file:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("🖼️ 上传的照片")
            image = Image.open(uploaded_file)
            st.image(image, use_container_width=True)
            
            # 显示照片信息
            st.caption(f"文件名: {uploaded_file.name}")
            st.caption(f"文件大小: {uploaded_file.size / 1024:.1f} KB")
            st.caption(f"图片尺寸: {image.size[0]} x {image.size[1]}")
        
        with col2:
            st.subheader("🤖 OCR 辨识")
            
            if st.button("🚀 开始辨识", type="primary", use_container_width=True):
                with st.spinner("正在使用双引擎 OCR 辨识中..."):
                    try:
                        image_bytes = uploaded_file.getvalue()
                        
                        # 执行 OCR（不需要 Google credentials 也能使用 Tesseract）
                        # 如果未登入，orchestrator 将在内部处理（使用 Tesseract）
                        # 如果已登入，它会使用完整的双引擎
                        if 'orchestrator' not in st.session_state or st.session_state.orchestrator is None:
                            creds = st.session_state.auth_manager.get_credentials()
                            st.session_state.orchestrator = OCROrchestrator(creds)

                        result = st.session_state.orchestrator.process_image(
                            image_bytes, 
                            photo_id=f"uploaded_{uploaded_file.name}"
                        )
                        
                        if result and result.get('status') == 'success':
                            st.session_state.ocr_result = result
                            st.session_state.selected_photo = {
                                'id': 'uploaded',
                                'filename': uploaded_file.name,
                                'base_url': None  # 使用一致的 key 名称
                            }
                            st.success("✅ 辨识完成！")
                        else:
                            error_msg = result.get('error', '未知错误') if result else '处理失败'
                            st.error(f"❌ 辨识失败：{error_msg}")
                    
                    except Exception as e:
                        logger.error(f"上传照片 OCR 失败: {e}")
                        st.error(f"处理失败: {e}")
            
            if not st.session_state.authenticated:
                st.info("💡 提示：未登入时仅使用 Tesseract 引擎辨识")
                st.info("登入后可使用 Google Vision API 提升准确度")
    
    # 如果已有辨识结果，显示在下方
    if st.session_state.ocr_result and st.session_state.selected_photo and st.session_state.selected_photo.get('id') == 'uploaded':
        st.markdown("---")
        render_ocr_results()

def main():
    """主应用程式"""
    init_session_state()
    
    # 确保 orchestrator 在应用开始时就被初始化
    # --- 新增：处理 OAuth 回调 ---
    query_params = st.query_params
    auth_code = query_params.get("code")
    state = query_params.get("state")

    if auth_code and not st.session_state.authenticated:
        with st.spinner("正在完成 Google 登入..."):
            logger.info("检测到 URL 中的授权码，正在尝试认证...")
            
            # 恢复 flow 对象到 auth_manager 实例
            if st.session_state.oauth_flow:
                st.session_state.auth_manager._flow = st.session_state.oauth_flow
                logger.info("OAuth flow has been restored from session state.")

            # 将从 URL 获取的 code 和 state 传递给认证方法
            if st.session_state.auth_manager.authenticate_with_code(auth_code, state=state) and authenticate():
                logger.info("通过 URL 授权码认证成功。")
                # 清理 URL 中的 code 和 state，防止重复使用
                st.session_state.oauth_flow = None # 清理已使用的 flow
                st.session_state.oauth_url = None
                st.query_params.clear()
                st.rerun() # 重新运行脚本以刷新状态
            else:
                logger.error("使用 URL 中的授权码认证失败。")
                # 如果后端记录了更详细的错误，展示给用户以便排查
                detailed = None
                try:
                    detailed = st.session_state.auth_manager.last_error
                except Exception:
                    detailed = None

                if detailed:
                    st.error(f"授权失败：{detailed}。请检查 `config/client_secrets.json` 中的 redirect_uris 是否包含当前应用的回调地址（例如 http://localhost:8501）。")
                else:
                    st.error("授权码无效或已过期，请重新尝试登入。请确认你在授权页面复制的 code 参数完整且未过期（通常 1 分钟内使用）。")
                st.session_state.oauth_flow = None # 清理已使用的 flow
                st.query_params.clear()
    # --- 结束：处理 OAuth 回调 ---

    if st.session_state.orchestrator is None:
        creds = st.session_state.auth_manager.get_credentials()
        st.session_state.orchestrator = OCROrchestrator(creds)

    render_sidebar()
    
    st.title("🧾 OCR 收支辨识系统")
    st.markdown("手写收据智能辨识 | 双引擎 OCR | Google Sheets 整合")
    st.markdown("---")
    
    # 创建 tabs：上传照片（主要）和 Google Photos（可选）
    if not st.session_state.authenticated:
        # 未登入：只显示上传功能
        tab1, tab2 = st.tabs(["📤 上传照片", "📸 Google 相簿 (需登入)"])
        
        with tab1:
            render_upload_tab()
        
        with tab2:
            st.info("👈 请先在侧边栏登入 Google 帐号以使用此功能")
            st.markdown("""
            ### Google 相簿功能
            - 📸 从 Google 相簿选择照片
            - 🔄 自动同步照片列表
            - 💾 直接保存到 Google Sheets
            """)
    else:
        # 已登入：显示所有功能
        tab1, tab2, tab3, tab4 = st.tabs(["📤 上传照片", "📷 Google 相簿", "🖼️ 照片预览", "📝 辨识结果"])
        
        with tab1:
            render_upload_tab()
        
        with tab2:
            render_photo_gallery()
        
        with tab3:
            if st.session_state.selected_photo:
                render_image_viewer()
            else:
                st.info("请先在「上传照片」或「Google 相簿」选择照片")
        
        with tab4:
            if st.session_state.ocr_result:
                render_ocr_results()
            else:
                st.info("请先完成 OCR 辨识")

if __name__ == "__main__":
    main()
