import os
# This MUST be set before Flask and other imports that might use it.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file, flash # Keep flash for now
from src.auth.firebase_auth import FirebaseAuthManager
from src.processing.ocr_orchestrator import OCROrchestrator # Import the orchestrator
from src.utils.config import get_config
import logging
from src.export.excel_exporter import export_to_excel
from google.oauth2.credentials import Credentials

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
    access_token = data.get('accessToken') # Re-add accessToken handling

    if not id_token:
        return jsonify({'status': 'error', 'error': 'Missing idToken'}), 400

    user_info = auth_manager.verify_id_token(id_token)
    if not user_info:
        return jsonify({'status': 'error', 'error': 'Invalid Firebase idToken'}), 401
    
    session['user'] = user_info
    flash('您已成功登入！', 'success')
    
    # Restore the original logic to create temporary credentials from the access token
    if access_token:
        try:
            creds = Credentials(token=access_token)
            # Store the credentials as a dictionary in the session.
            # This credential will NOT be refreshable. It will expire.
            session['google_credentials'] = {
                'token': creds.token,
                'refresh_token': None,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }
            logging.info("Successfully stored temporary Google API credentials in session.")
        except Exception as e:
            logging.error(f"Failed to create credentials from access token: {e}")

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

    # Check for credentials, but don't redirect to the new login flow
    if 'google_credentials' not in session:
        return jsonify({'error': 'Google credentials not found in session. Please log out and log back in.'}), 401

    if 'invoiceImage' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['invoiceImage']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        try:
            # Initialize the orchestrator here, passing in session credentials
            creds_dict = session.get('google_credentials')
            if not creds_dict:
                 return jsonify({'error': 'Google credentials not found in session.'}), 401
            
            # The OCROrchestrator expects the credentials DICTIONARY, not the object.
            # It will build the credentials object internally.
            ocr_orchestrator = OCROrchestrator(google_credentials=creds_dict)

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


if __name__ == '__main__':
    # Disabled reloader to fix constant restarts from .venv changes.
    # For a better fix, move the .venv folder outside the project.
    app.run(debug=True, port=8501, use_reloader=False)