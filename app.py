import os
import logging
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file, flash
from src.auth.firebase_auth import FirebaseAuthManager
from src.processing.ocr_orchestrator import OCROrchestrator
from src.utils.config import get_config
from src.export.excel_exporter import export_to_excel
from google.oauth2.credentials import Credentials

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

    auth_manager = FirebaseAuthManager()

    @app.route('/login')
    def login():
        return render_template('login.html', config=app.config['FIREBASE_CONFIG'])

    @app.route('/sessionLogin', methods=['POST'])
    def session_login():
        data = request.get_json()
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
        
        return render_template('index.html', user=session['user'])

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
        
        file = request.files['invoiceImage']

        try:
            # Initialize the orchestrator for each request with the user's session credentials.
            ocr_orchestrator = OCROrchestrator(google_credentials=creds_dict)

            image_bytes = file.read()
            logger.info(f"User '{session['user'].get('name')}' uploaded file: {file.filename}, size: {len(image_bytes)} bytes")
            
            ocr_result = ocr_orchestrator.process_image(image_bytes, photo_id=file.filename)
            
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

        data = request.get_json()
        raw_text = data.get('raw_text')
        original_ocr_result = data.get('ocr_result')
        expense_keywords = data.get('expense_keywords') # Get keywords from request

        if not raw_text:
            return jsonify({'error': 'No raw_text provided'}), 400

        try:
            # We can initialize a dummy orchestrator since we don't need OCR engines.
            # The parsing logic is self-contained.
            orchestrator = OCROrchestrator()
            # Pass keywords to the reprocess_text method
            reparsed_result = orchestrator.reprocess_text(raw_text, original_ocr_result, expense_keywords=expense_keywords)
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