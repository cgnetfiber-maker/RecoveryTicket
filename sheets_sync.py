import os
import json
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe

def upload_dataframe_to_sheet(df: pd.DataFrame):
    """Uploads a pandas DataFrame to Google Sheets using environment variables."""
    # Read environment variables
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    worksheet_gid = os.getenv("GOOGLE_WORKSHEET_GID")
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    if not service_account_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable is missing.")

    # Authenticate
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_dict = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    # Open Spreadsheet & Target Worksheet
    spreadsheet = gc.open_by_key(spreadsheet_id)
    
    if worksheet_gid:
        worksheet = spreadsheet.get_worksheet_by_id(int(worksheet_gid))
    else:
        worksheet = spreadsheet.get_worksheet(0)

    # Clear old data and write the new DataFrame
    worksheet.clear()
    set_with_dataframe(worksheet, df, include_index=False, include_column_header=True)
    return "Data successfully synced to Google Sheets!"
