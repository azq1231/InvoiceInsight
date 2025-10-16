"""Google Sheets API integration for data export"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class GoogleSheetsAPI:
    """Google Sheets API client for exporting OCR results"""
    
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self.service = build('sheets', 'v4', credentials=credentials)
        self.config = get_config()
        logger.info("Google Sheets API client initialized")
    
    def create_spreadsheet(self, title: str) -> Dict[str, str]:
        """Create a new spreadsheet"""
        try:
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            
            result = self.service.spreadsheets().create(
                body=spreadsheet,
                fields='spreadsheetId,spreadsheetUrl'
            ).execute()
            
            logger.info(f"Spreadsheet created: {result.get('spreadsheetId')}")
            return {
                'id': result.get('spreadsheetId'),
                'url': result.get('spreadsheetUrl')
            }
        except Exception as e:
            logger.error(f"Failed to create spreadsheet: {e}")
            raise
    
    def append_rows(self, spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> Dict:
        """Append rows to spreadsheet"""
        try:
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.info(f"Appended {len(values)} rows to spreadsheet")
            return result
        except Exception as e:
            logger.error(f"Failed to append rows: {e}")
            raise
    
    def get_spreadsheet_info(self, spreadsheet_id: str) -> Dict:
        """Get spreadsheet metadata"""
        try:
            result = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            return {
                'id': result.get('spreadsheetId'),
                'title': result.get('properties', {}).get('title'),
                'url': result.get('spreadsheetUrl'),
                'sheets': [
                    {
                        'id': sheet.get('properties', {}).get('sheetId'),
                        'title': sheet.get('properties', {}).get('title')
                    }
                    for sheet in result.get('sheets', [])
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get spreadsheet info: {e}")
            raise
    
    def export_ocr_results(self, spreadsheet_id: str, ocr_results: List[Dict]) -> Dict:
        """Export OCR results to spreadsheet"""
        try:
            rows = []
            rows.append(['日期', '項目', '金額', '分類', '狀態', '辨識時間', '照片ID'])
            
            for result in ocr_results:
                date = result.get('date', '')
                photo_id = result.get('photo_id', '')
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                for item in result.get('items', []):
                    rows.append([
                        date,
                        item.get('name', ''),
                        item.get('amount', 0),
                        item.get('category', '支出'),
                        '需確認' if item.get('needs_review', False) else '已確認',
                        timestamp,
                        photo_id
                    ])
            
            return self.append_rows(spreadsheet_id, 'Sheet1!A:G', rows)
            
        except Exception as e:
            logger.error(f"Failed to export OCR results: {e}")
            raise
