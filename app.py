import os
import logging
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file, flash
from src.auth.firebase_auth import FirebaseAuthManager
from src.processing.ocr_orchestrator import OCROrchestrator
from src.processing.reparser import Reparser
from src.processing.general_ledger_parser import SPECIAL_EXPENSE_KEYWORDS as DEFAULT_EXPENSE_KEYWORDS
from src.utils.config import get_config
from src.export.excel_exporter import export_to_excel
from google.oauth2.credentials import Credentials
from src.user_settings import UserSettingsManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Application Factory Pattern"""
    app = Flask(__name__)

    # --- Configuration ---
    config = get_config()
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
    app.config['FIREBASE_CONFIG'] = config.get('firebase.web_app_config')
    
    # Security warning for default secret key
    if not app.config['SECRET_KEY']:
        logger.warning("FLASK_SECRET_KEY is not set! Using a default, insecure key for development.")
        app.config['SECRET_KEY'] = 'a_default_secret_key_for_dev_do_not_use_in_prod'

    # This allows OAuth to run over HTTP for local development.
    # In production, you MUST use HTTPS and remove this.
    if app.debug:
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        logger.warning("OAUTHLIB_INSECURE_TRANSPORT is enabled. This is not safe for production.")

    @app.route('/login')
    def login():
        return render_template('login.html', config=app.config['FIREBASE_CONFIG'])

    @app.route('/sessionLogin', methods=['POST'])
    def session_login():
        data = request.get_json()
        auth_manager = FirebaseAuthManager()
        id_token = data.get('idToken')
        access_token = data.get('accessToken')

        if not id_token:
            logger.warning("Session login attempt failed: Missing idToken.")
            return jsonify({'status': 'error', 'error': 'Missing idToken'}), 400

        user_info = auth_manager.verify_id_token(id_token)
        if not user_info:
            logger.warning("Session login attempt failed: Invalid Firebase idToken.")
            return jsonify({'status': 'error', 'error': 'Invalid Firebase idToken'}), 401
        
        session['user'] = user_info
        flash('您已成功登入！', 'success')
        
        # Create temporary, non-refreshable credentials from the access token.
        # This is sufficient for short-lived API calls within the user's session.
        if access_token:
            try:
                creds = Credentials(token=access_token)
                session['google_credentials'] = {
                    'token': creds.token,
                    'refresh_token': None, # This token cannot be refreshed
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes
                }
                logger.info(f"User '{user_info.get('name')}' logged in. Stored temporary Google API credentials in session.")
            except Exception as e:
                logger.error(f"Failed to create credentials from access token for user '{user_info.get('name')}': {e}")

        return jsonify({'status': 'success', 'redirectUrl': url_for('index')})


    @app.route('/')
    def index():
        if 'user' not in session:
            return redirect(url_for('login'))
        
        settings_manager = UserSettingsManager()
        user_id = session['user'].get('id', '')
        # Get user-specific keywords. If they don't exist, use the default ones.
        user_keywords = settings_manager.get_expense_keywords(user_id)
        if user_keywords is None:
            user_keywords = DEFAULT_EXPENSE_KEYWORDS

        return render_template('index.html', user=session['user'], saved_keywords=','.join(user_keywords))

    @app.route('/settings', methods=['GET', 'POST'])
    def settings():
        if 'user' not in session:
            return redirect(url_for('login'))
        
        settings_manager = UserSettingsManager()
        user_id = session['user'].get('id', '')

        if request.method == 'POST':
            keywords_str = request.form.get('keywords', '')
            # Split by newline, strip whitespace, and filter out empty lines
            keywords_list = [k.strip() for k in keywords_str.splitlines() if k.strip()]
            settings_manager.save_expense_keywords(user_id, keywords_list)
            # Also update the session to reflect the change immediately
            session['user_keywords'] = keywords_list
            flash('關鍵字設定已成功儲存！', 'success')
            return redirect(url_for('settings'))

        user_keywords = settings_manager.get_expense_keywords(user_id)
        if user_keywords is None:
            user_keywords = DEFAULT_EXPENSE_KEYWORDS
        
        return render_template('settings.html', user=session['user'], keywords=user_keywords)

    @app.route('/get_keywords', methods=['GET'])
    def get_keywords():
        """An API endpoint to fetch the user's current keywords."""
        if 'user' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        settings_manager = UserSettingsManager()
        user_id = session['user'].get('id', '')
        user_keywords = settings_manager.get_expense_keywords(user_id)
        if user_keywords is None:
            user_keywords = DEFAULT_EXPENSE_KEYWORDS
        
        return jsonify({'keywords': user_keywords})

    @app.route('/upload', methods=['POST'])
    def upload_file():
        if 'user' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        creds_dict = session.get('google_credentials')
        if not creds_dict:
            logger.warning(f"Upload failed for user '{session['user'].get('name')}': Google credentials not found in session.")
            return jsonify({'error': 'Google credentials not found. Please log out and log back in.'}), 401

        if 'invoiceImage' not in request.files or not request.files['invoiceImage'].filename:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files.get('invoiceImage')
        keywords_str = request.form.get('expense_keywords', '')
        expense_keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]

        try:
            # Initialize the orchestrator for each request with the user's session credentials.
            ocr_orchestrator = OCROrchestrator(google_credentials=creds_dict)

            image_bytes = file.read()
            logger.info(f"User '{session['user'].get('name')}' uploaded file: {file.filename}, size: {len(image_bytes)} bytes")
            
            ocr_result = ocr_orchestrator.process_image(image_bytes, photo_id=file.filename, expense_keywords=expense_keywords)
            
            # Store result in session for export
            if ocr_result.get('status') == 'success':
                session['last_result'] = ocr_result

            logger.info(f"OCR Result from {ocr_result.get('ocr_result', {}).get('engine', 'unknown')} engine for {file.filename}")
            return jsonify(ocr_result)
        except Exception as e:
            logger.error(f"OCR processing failed for file '{file.filename}': {e}", exc_info=True)
            return jsonify({'error': f'Failed to process image: {e}'}), 500

    @app.route('/reparse', methods=['POST'])
    def reparse_text():
        """
        Re-runs the parsing and validation logic on existing raw OCR text
        without performing OCR again. This is for quick debugging of the parser.
        """
        if 'user' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        reparser = Reparser()
        data = request.get_json()
        ocr_result = data.get('ocr_result')
        expense_keywords = data.get('expense_keywords') # Get keywords from request

        if not ocr_result or 'full_text' not in ocr_result:
            return jsonify({'error': 'No ocr_result with full_text provided'}), 400

        try:
            # Use the new, lightweight Reparser which has no external dependencies.
            reparsed_result = reparser.reprocess(ocr_result, expense_keywords=expense_keywords)
            return jsonify(reparsed_result)
        except Exception as e:
            logger.error(f"Reparsing failed: {e}", exc_info=True)
            return jsonify({'error': f'Failed to reparse text: {e}'}), 500

    @app.route('/logout')
    def logout():
        user_name = session.get('user', {}).get('name', 'Unknown user')
        session.clear()
        logger.info(f"User '{user_name}' logged out.")
        return redirect(url_for('login'))

    @app.route('/export')
    def export_file():
        if 'user' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        if 'last_result' not in session:
            return jsonify({'error': 'No data to export. Please process an image first.'}), 400

        try:
            processed_data = session['last_result']
            file_path = export_to_excel(processed_data)
            
            return send_file(
                file_path,
                as_attachment=True,
                download_name=os.path.basename(file_path)
            )
        except Exception as e:
            logger.error(f"Excel export failed for user '{session['user'].get('name')}': {e}", exc_info=True)
            return jsonify({'error': f'Failed to export file: {e}'}), 500

    return app

if __name__ == '__main__':
    app = create_app()
    # For production, use a proper WSGI server like Gunicorn or uWSGI.
    # Example: gunicorn --bind 0.0.0.0:8501 "app:create_app()"
    app.run(host='0.0.0.0', port=8501, debug=True)