---
title: SSRMS Ticket Scraper
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# SSRMS Ticket Scraper

This project runs a lightweight browser automation app that logs into the SSRMS portal, filters My Case, reads the ticket list, and exports it as CSV for download.

## Run locally

```bash
pip install -r requirements.txt
python -m playwright install chromium
python app.py
```

Then open the local URL shown in the terminal.

For the standalone scraper, set credentials in the environment before running it:

```powershell
$env:SSRMS_USERNAME = "your username"
$env:SSRMS_PASSWORD = "your password"
python KiranTicketScrapper.py
```

## Deploy to Hugging Face Spaces

1. Create a new Hugging Face Space.
2. Choose the `Docker` template.
3. Upload this project folder or connect it to a GitHub repository.
4. Use a Space secret for the credentials if you do not want them in the app UI.
5. Launch the Space.

## Notes

- Do not paste production credentials into the repo.
- Use the browser form in the app or store secrets in Hugging Face Space Secrets.
- The app uses a headless Chromium browser, which is supported in a Dockerized HF Space.

## Important

This application interacts with a third-party system. Please ensure you have permission to automate and scrape the site according to that organization’s rules.

