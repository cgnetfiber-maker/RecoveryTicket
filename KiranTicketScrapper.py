import os
import re
import time
from pathlib import Path

import pandas as pd
from sheets_sync import upload_dataframe_to_sheet
from playwright.sync_api import sync_playwright


LOGIN_URL = "https://billing.cgnet.com.np/h8ssrms/Login.aspx?redir=true"
CASE_URL = "https://billing.cgnet.com.np/h8ssrms/CaseListMin.aspx"
EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", "exports"))


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


def scrape_tickets(username: str, password: str, page_size: str = "500") -> pd.DataFrame:
    """Log in to SSRMS and return all rows from the My Case ticket list."""
    if not username or not password:
        raise ValueError("SSRMS_USERNAME and SSRMS_PASSWORD are required.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
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

            my_case = page.locator("#ContentPlaceHolder1_cbMycase")
            if my_case.count() and not my_case.is_checked():
                my_case.evaluate("element => element.click()")
                page.wait_for_timeout(2500)

            page_size_select = page.locator("#ContentPlaceHolder1_ddlPageSize")
            if page_size_select.count():
                page_size_select.select_option(value=page_size)
                page.wait_for_timeout(4000)

            table_selector = "#ContentPlaceHolder1_gdcase"
            if not page.locator(table_selector).count():
                table_selector = "table"

            headers = _read_headers(page.locator(table_selector).first)
            records = []
            seen_pages = set()
            page_number = 1

            while page_number <= 500:
                table = page.locator(table_selector).first
                page_rows = _read_rows(table, len(headers))
                if not page_rows:
                    break

                signature = tuple(tuple(row) for row in page_rows)
                if signature in seen_pages:
                    break
                seen_pages.add(signature)
                records.extend(page_rows)

                next_link = _find_next_link(page, page_number)
                if next_link is None:
                    break
                previous_signature = signature
                next_link.click()
                page.wait_for_function(
                    """([selector, previous]) => {
                        const table = document.querySelector(selector);
                        if (!table) return false;
                        const rows = Array.from(table.querySelectorAll('tr'));
                        const current = rows.slice(1).map(row => row.innerText.trim()).join('|');
                        return current && current !== previous;
                    }""",
                    arg=[table_selector, "|".join(" ".join(row) for row in previous_signature)],
                    timeout=15000,
                )
                page_number += 1

            if not records:
                raise RuntimeError("No ticket rows found. Check credentials and the My Case filter.")

            return pd.DataFrame(records, columns=headers)
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
        page.goto(CASE_URL, wait_until="domcontentloaded", timeout=60000)


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


def _read_headers(table):
    header_cells = table.locator("tr").first.locator("th, td")
    headers = [header_cells.nth(i).inner_text().strip() for i in range(header_cells.count())]
    headers = [header or f"Column {i + 1}" for i, header in enumerate(headers)]
    return headers or ["Ticket data"]


def _read_rows(table, column_count):
    rows = table.locator("tr")
    records = []
    for row_index in range(1, rows.count()):
        cells = rows.nth(row_index).locator("td")
        values = [value.replace("\n", " ").strip() for value in cells.all_inner_texts()]
        if not values or not any(values) or len(values) == 1:
            continue
        records.append(_align_row_to_headers(values, column_count))
    return records


def _find_next_link(page, page_number):
    next_number = str(page_number + 1)
    numbered_links = page.locator(
        "#ContentPlaceHolder1_gdcase a[href*='Page$'], "
        "#ContentPlaceHolder1_gdcase a[href*='__doPostBack'], "
        "#ContentPlaceHolder1_gdcase a[href*='javascript']"
    )
    for index in range(numbered_links.count()):
        link = numbered_links.nth(index)
        if link.inner_text().strip() == next_number and link.is_enabled():
            return link

    arrows = page.locator("#ContentPlaceHolder1_gdcase a").filter(
        has_text=re.compile(r"^(Next|>|>>|›|»)$", re.IGNORECASE)
    )
    return arrows.last if arrows.count() and arrows.last.is_enabled() else None


def main():
    tickets = scrape_tickets(
        os.environ.get("SSRMS_USERNAME", ""),
        os.environ.get("SSRMS_PASSWORD", ""),
    )
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = EXPORT_DIR / f"cases_{int(time.time())}.csv"
    tickets.to_csv(output_path, index=False)
    upload_dataframe_to_sheet(tickets)
    print(f"Saved {len(tickets)} tickets to {output_path}")


if __name__ == "__main__":
    main()
