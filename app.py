import gradio as gr
from KiranTicketScrapper import run_scraper
# In app.py
from KiranTicketScrapper import scrape_tickets  # Use your actual function name here
def start_scraping():
    try:
        run_scraper()
        return "Scraping & Google Sheets Sync Completed Successfully!"
    except Exception as e:
        return f"Error occurred: {str(e)}"

with gr.Blocks(title="RecoveryTicket Scraper") as demo:
    gr.Markdown("# SSRMS RecoveryTicket Scraper")
    status_output = gr.Textbox(label="Status Logs")
    run_button = gr.Button("Start Scraping Task")
    
    run_button.click(fn=start_scraping, outputs=status_output)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
