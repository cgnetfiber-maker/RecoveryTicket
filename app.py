import os
import re
import time
from pathlib import Path

import gradio as gr
import pandas as pd
from sheets_sync import upload_dataframe_to_sheet
from playwright.sync_api import sync_playwright


DEFAULT_PAGE_SIZE = "500"
EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", "exports"))
TARGET_URL = "https://billing.cgnet.com.np/h8ssrms/CaseListMin.aspx"
LOGIN_URL = "https://billing.cgnet.com.np/h8ssrms/Login.aspx?redir=true"


def _align_row_to_headers(values, column_count):
    normalized = [str(value).replace("\n", " ").strip() for value in values]

    while len(normalized) > column_count:
        if normalized and normalized[0] in {"", "Select", "select", "checkbox"}:
            normalized.pop(0)
            continue
        if normalized and normalized[-1] in {"", "Select", "select", "checkbox"}:
            normalized.pop()
            continue
        normalized = normalized[:column_count]
        break

    if len(normalized) < column_count:
        normalized.extend([""] * (column_count - len(normalized)))

    return normalized[:column_count]


def _scrape_case_table(username: str, password: str, page_size: str = DEFAULT_PAGE_SIZE, my_case: bool = True):
    if not username or not password:
        raise ValueError("Username and password are required.")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        try:
            context = browser.new_context(
                viewport={"width": 1600, "height": 1100},
                extra_http_headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            )
            page = context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            page.fill("#txtUserName", username)
            page.fill("#txtPassword", password)
            page.locator("input#save").click(force=True)

            # The portal may redirect to different pages after a successful login.
            page.wait_for_timeout(3000)

            _open_case_page(page)
            _open_detail_view(page)
            _configure_case_settings(page)
            page.wait_for_timeout(2500)

            if page.locator("#txtUserName").count() or page.locator("#txtPassword").count():
                raise RuntimeError("Login failed. Check the SSRMS username and password.")

            if my_case:
                my_case_box = page.locator("#ContentPlaceHolder1_cbMycase")
                if my_case_box.count() > 0:
                    my_case_box.evaluate("element => element.click()")
                    page.wait_for_timeout(2500)

            page_size_select = page.locator("#ContentPlaceHolder1_ddlPageSize")
            if page_size_select.count() > 0:
                try:
                    page_size_select.select_option(value=str(page_size))
                    page.wait_for_timeout(4000)
                except Exception:
                    # Some SSRMS deployments do not offer every page-size value.
                    pass

            page.wait_for_timeout(3000)

            table_selector = "#ContentPlaceHolder1_gdcase"
            table = page.locator(table_selector)
            if table.count() == 0:
                table = page.locator("table").filter(has_text="Ticket No").first
                table_selector = None

            rows = table.locator("tr")
            header_row = rows.first.locator("th, td")
            headers = []
            for i in range(header_row.count()):
                value = header_row.nth(i).inner_text().strip()
                if value:
                    headers.append(value)

            if not headers:
                headers = [
                    "Ticket No",
                    "Date",
                    "User Id",
                    "Name",
                    "Contact No",
                    "Status",
                    "Last Modified Date",
                    "Team",
                    "Last Remark",
                ]

            data = []
            seen_pages = set()
            page_number = 1
            while page_number <= 500:
                table = page.locator(table_selector) if table_selector else page.locator("table").filter(has_text="Ticket No").first
                rows = table.locator("tr")
                page_data = []
                for row_idx in range(1, rows.count()):
                    cells = rows.nth(row_idx).locator("td")
                    values = [value.replace("\n", " ").strip() for value in cells.all_inner_texts()]

                    if not any(values) or len(values) == 1:
                        continue

                    page_data.append(_align_row_to_headers(values, len(headers)))

                if not page_data:
                    if not data:
                        raise ValueError("No ticket rows were found after logging in. Check your credentials or filters.")
                    break

                page_signature = tuple(tuple(row) for row in page_data)
                if page_signature in seen_pages:
                    break
                seen_pages.add(page_signature)
                data.extend(page_data)

                pager_scope = page.locator(table_selector) if table_selector else page.locator("table").filter(has_text="Ticket No").first
                pager_links = pager_scope.locator(
                    "a[href*='Page$'], a[href*='__doPostBack'], a[href*='javascript']"
                )
                next_link = None
                next_page_number = str(page_number + 1)
                for link_idx in range(pager_links.count()):
                    link = pager_links.nth(link_idx)
                    text = link.inner_text().strip()
                    if text == next_page_number and link.is_enabled():
                        next_link = link
                        break

                if next_link is None:
                    arrow_links = pager_scope.locator("a").filter(
                        has_text=re.compile(r"^(Next|>|>>|\u203a|\u00bb)$", re.IGNORECASE)
                    )
                    if arrow_links.count() > 0 and arrow_links.last.is_enabled():
                        next_link = arrow_links.last

                if next_link is None:
                    break

                previous_signature = page_signature
                next_link.click()
                if table_selector:
                    page.wait_for_function(
                        """([selector, previous]) => {
                            const table = document.querySelector(selector);
                            if (!table) return false;
                            const current = Array.from(table.querySelectorAll('tr'))
                                .slice(1).map(row => row.innerText.trim()).join('|');
                            return current && current !== previous;
                        }""",
                        arg=[table_selector, "|".join(" ".join(row) for row in previous_signature)],
                        timeout=15000,
                    )
                else:
                    page.wait_for_timeout(2000)
                page_number += 1

            if not data:
                raise ValueError("No ticket rows were found after applying the filter.")

            df = pd.DataFrame(data, columns=headers)
            return df
        finally:
            browser.close()


def _open_case_page(page):
    """Open Customer Care > Case, with a direct URL fallback."""
    try:
        customer_care = page.get_by_text("Customer Care", exact=True).first
        if customer_care.count() == 0:
            raise RuntimeError("Customer Care menu was not found")
        customer_care.click()
        page.wait_for_timeout(1000)

        case_link = page.get_by_text("Case", exact=True).first
        if case_link.count() == 0:
            raise RuntimeError("Case menu was not found")
        case_link.click()
        page.wait_for_load_state("domcontentloaded", timeout=30000)

    except Exception:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)


def _configure_case_settings(page):
    selected_fields = {
        "Date",
        "Ticket No",
        "User Id",
        "Title",
        "Name",
        "Address",
        "Contact No",
        "Status",
        "Category",
        "Sub Category",
        "Team",
        "Last Modified Date",
        "Last Remark",
    }
    setting_button = page.locator("#ContentPlaceHolder1_btnsetting")
    if setting_button.count():
        setting_button.evaluate("element => element.click()")
        page.wait_for_timeout(500)

    checkboxes = page.locator("input[id^='ContentPlaceHolder1_chklistcasesetting_']")
    page.wait_for_selector("#ContentPlaceHolder1_chklistcasesetting_11", state="attached", timeout=30000)
    if checkboxes.count() == 0:
        raise RuntimeError("Case settings fields were not found.")
    for index in range(checkboxes.count()):
        checkbox = checkboxes.nth(index)
        should_be_checked = checkbox.input_value() in selected_fields
        if checkbox.is_checked() != should_be_checked:
            checkbox.set_checked(should_be_checked)

    save_button = page.locator("#ContentPlaceHolder1_btnsavecasesetting")
    if save_button.count():
        save_button.evaluate("element => element.click()")
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)


def _open_detail_view(page):
    detail_view = page.locator("#ContentPlaceHolder1_btnMoreInfo")
    if detail_view.count() == 0:
        raise RuntimeError("Detail View control was not found")
    detail_view.evaluate("element => element.click()")
    page.wait_for_load_state("domcontentloaded", timeout=30000)


def run_scraper(username: str, password: str, page_size: str = DEFAULT_PAGE_SIZE, my_case: bool = True):
    try:
        df = _scrape_case_table(username=username, password=password, page_size=page_size, my_case=my_case)
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = EXPORT_DIR / f"cases_{int(time.time())}.csv"
        df.to_csv(csv_path, index=False)
        try:
            upload_dataframe_to_sheet(df)
        except Exception as exc:
            gr.Warning(f"Tickets scraped, but Google Sheets sync was skipped: {exc}")
        return df, str(csv_path)
    except Exception as exc:  # pragma: no cover - UI layer handles exception
        raise gr.Error(str(exc)) from exc


def build_ui():
    with gr.Blocks(title="SSRMS Ticket Scraper") as demo:
        gr.Markdown(
            """
            # SSRMS Ticket Scraper

            Log in to SSRMS, filter My Case, and export the ticket list into a table and CSV file.
            """
        )

        with gr.Row():
            username = gr.Textbox(label="Username", placeholder="your username")
            password = gr.Textbox(label="Password", type="password", placeholder="your password")

        page_size = gr.Dropdown(
            choices=["10", "20", "50", "100", "200", "300", "500"],
            value=DEFAULT_PAGE_SIZE,
            label="Page size",
        )
        my_case = gr.Checkbox(label="My Case only", value=True)

        submit = gr.Button("Scrape tickets")

        with gr.Row():
            output = gr.DataFrame(label="Ticket data")
            csv_file = gr.File(label="Download CSV")

        submit.click(
            fn=run_scraper,
            inputs=[username, password, page_size, my_case],
            outputs=[output, csv_file],
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    share = os.environ.get("GRADIO_SHARE", "false").lower() == "true"
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
        share=share,
    )
