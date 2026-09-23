# RecoveryTicket Scraper & Google Sheets Sync

An automated Playwright-based scraper and web dashboard built to fetch ticket recovery data from SSRMS and synchronize structured updates directly into Google Sheets.

---

## Features

- **Automated Scraping:** Uses Playwright to interact headlessly with the SSRMS portal.
- **Google Sheets Integration:** Automatically authenticates via Google Service Account credentials (`gspread`) to push structured updates.
- **Gradio UI:** Interactive web interface to manually trigger recovery tasks, view logs, and track execution status.
- **Dockerized Architecture:** Pre-configured with headless browser binaries for deployment on Hugging Face Spaces or Render.

---

## Project Structure

```text
├── Dockerfile                   # Docker container configuration & system dependencies
├── README.md                    # Project documentation
├── requirements.txt             # Python dependencies
├── app.py                       # Gradio web interface launcher
├── KiranTicketScrapper.py       # Core Playwright scraping logic
└── sheets_sync.py               # Google Sheets API handler (gspread)
