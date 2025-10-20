import os
# This MUST be set before Flask and other imports that might use it.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file, flash
from src.auth.firebase_auth import FirebaseAuthManager
from src.processing.ocr_orchestrator import OCROrchestrator # Import the orchestrator
from src.utils.config import get_config
import logging
from src.export.excel_exporter import export_to_excel

# --- New Imports for Google OAuth Test ---
from src.auth.google_auth import GoogleAuthManager
from google.oauth2.credentials import Credentials
import requests as grequests # Alias to avoid conflict with flask.request
# --- End New Imports ---

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

auth_manager = FirebaseAuthManager()
config = get_config()
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'a_default_secret_key_for_dev')

# REMOVED: Global OCR engine initialization

@app.route('/login')
def login():
    firebase_config = config.get('firebase.web_app_config')
    return render_template('login.html', config=firebase_config)

@app.route('/sessionLogin', methods=['POST'])
def session_login():
    data = request.get_json()
    id_token = data.get('idToken')
    access_token = data.get('accessToken')

    if not id_token:
        return jsonify({'status': 'error', 'error': 'Missing idToken'}), 400

    user_info = auth_manager.verify_id_token(id_token)
    if not user_info:
        return jsonify({'status': 'error', 'error': 'Invalid idToken'}), 401
    
    session['user'] = user_info
    flash('您已成功登入！', 'success')
    
    # Create a credentials object from the access token and store it for the orchestrator
    if access_token:
        try:
            creds = Credentials(token=access_token)
            # The OCROrchestrator expects a dictionary, so we build one.
            # Note: This credential will not be refreshable as we don't get a refresh token from this flow.
            session['google_credentials'] = {
                'token': creds.token,
                'refresh_token': creds.refresh_token, # will be None
                'token_uri': creds.token_uri, # will be None
                'client_id': creds.client_id, # will be None
                'client_secret': creds.client_secret, # will be None
                'scopes': creds.scopes # will be None
            }
            logging.info("Successfully stored Google API credentials in session.")
        except Exception as e:
            logging.error(f"Failed to create credentials from access token: {e}")
            # Proceed with login, but API calls might fail later.
            pass

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

    if 'invoiceImage' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['invoiceImage']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        try:
            # Initialize the orchestrator here, passing in session credentials
            google_creds = session.get('google_credentials')
            ocr_orchestrator = OCROrchestrator(google_credentials=google_creds)

            image_bytes = file.read()
            logging.info(f"Received file: {file.filename}, size: {len(image_bytes)} bytes")
            
            # Use the orchestrator instance to process the image
            ocr_result = ocr_orchestrator.process_image(image_bytes, photo_id=file.filename)
            
            # Store result in session for export
            if ocr_result.get('status') == 'success':
                session['last_result'] = ocr_result

            logging.info(f"OCR Result from {ocr_result.get('ocr_result', {}).get('engine', 'unknown')} engine: {ocr_result.get('ocr_result', {}).get('full_text', '')[:100]}...")
            return jsonify(ocr_result)
        except Exception as e:
            logging.error(f"OCR processing failed: {e}", exc_info=True) # Add exc_info for better debugging
            return jsonify({'error': f'Failed to process image: {e}'}), 500
    
    return jsonify({'error': 'Unknown error'}), 500

@app.route('/logout')
def logout():
    session.clear() # Clear the entire session on logout
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
        
        # Use send_file to send the generated file
        return send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path)
        )
    except Exception as e:
        logging.error(f"Excel export failed: {e}", exc_info=True)
        return jsonify({'error': f'Failed to export file: {e}'}), 500

# --- End New Routes ---


if __name__ == '__main__':
    # Disabled reloader to fix constant restarts from .venv changes.
    # For a better fix, move the .venv folder outside the project.
    app.run(debug=True, port=8501, use_reloader=False)