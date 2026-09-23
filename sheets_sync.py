import os
import json
import gspread
from google.oauth2.service_account import Credentials

# 1. Fetch values from Render Environment Variables
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "1SyhE9nQf3LV8QEBTCLavgfr8w45y-mI69XPbtuN2hPA")
WORKSHEET_GID = os.getenv("GOOGLE_WORKSHEET_GID", "84560511")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

# 2. Authenticate
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)

# 3. Open Spreadsheet and Target Sheet by GID
spreadsheet = gc.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.get_worksheet_by_id(int(WORKSHEET_GID))
