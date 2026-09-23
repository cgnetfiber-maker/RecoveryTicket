import os
from pathlib import Path

import gspread
import pandas as pd


DEFAULT_SPREADSHEET_ID = "1SyhE9nQf3LV8QEBTCLavgfr8w45y-mI69XPbtuN2hPA"
DEFAULT_WORKSHEET_NAME = "Ticket"


def upload_dataframe_to_sheet(dataframe: pd.DataFrame) -> None:
    credentials_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not credentials_path:
        raise RuntimeError(
            "Set GOOGLE_SERVICE_ACCOUNT_FILE to a Google service-account JSON file "
            "before running the scraper."
        )

    credentials_file = Path(credentials_path)
    if not credentials_file.is_file():
        raise RuntimeError(f"Google service-account file was not found: {credentials_file}")

    spreadsheet_id = os.environ.get("GOOGLE_SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID)
    worksheet_name = os.environ.get("GOOGLE_WORKSHEET_NAME", DEFAULT_WORKSHEET_NAME)
    client = gspread.service_account(filename=str(credentials_file))
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)

    values = [dataframe.columns.tolist()]
    for row in dataframe.itertuples(index=False, name=None):
        values.append(["" if pd.isna(value) else value for value in row])

    worksheet.clear()
    if values:
        worksheet.update(values=values, range_name="A1", raw=True)