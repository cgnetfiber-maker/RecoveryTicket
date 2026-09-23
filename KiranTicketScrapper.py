from playwright.sync_api import sync_playwright

def run_scraper():
    with sync_playwright() as p:
        # Launch Chromium with memory and sandbox optimizations
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-zygote",
                "--single-process"  # Prevents spawning multiple RAM-heavy processes
            ]
        )
        context = browser.new_context()
        page = context.new_page()
        
        # Add a timeout so it doesn't hang indefinitely
        page.set_default_timeout(60000)
        
        # --- Your Scraping Logic Here ---
        
        browser.close()
