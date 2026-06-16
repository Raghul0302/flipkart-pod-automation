import os
import time
import gspread

from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# =====================================================
# IMPORTANT
# =====================================================
# BEFORE RUNNING:
#
# 1. Open separate automation Chrome:
#
# "C:\Program Files\Google\Chrome\Application\chrome.exe"
# --remote-debugging-port=9222
# --user-data-dir="C:\flipkart_pod_automation\chrome_profile"
#
# 2. Login VendorHub
#
# 3. Go to:
#       Payments → Invoices
#
# 4. Set FY manually:
#       2025 - 2026
#
# 5. Keep browser open
#
# 6. Run:
#       python main.py
# =====================================================

# =====================================================
# GOOGLE SHEET
# =====================================================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials.json",
    scope
)

client = gspread.authorize(creds)

# =====================================================
# OPEN SHEET USING SHEET ID
# =====================================================

sheet = client.open_by_key(
    "1AVgYzZDmevcBNF0LscogMZMtu2rhJasQtxn_vx8JpPo"
).worksheet("Sheet3")

# =====================================================
# GOOGLE DRIVE
# =====================================================

drive_creds = Credentials.from_authorized_user_file(
    "token.json",
    ["https://www.googleapis.com/auth/drive"]
)

drive_service = build(
    "drive",
    "v3",
    credentials=drive_creds
)

# =====================================================
# POD_UPLOAD_MAIN FOLDER ID
# =====================================================

FOLDER_ID = "1TEQ6bET8n2GdzBMF_Aofs5oMWekkA8bG"

# =====================================================
# DOWNLOAD FOLDER
# =====================================================

DOWNLOAD_PATH = r"C:\flipkart_pod_automation\downloads"

os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# =====================================================
# PLAYWRIGHT
# =====================================================

with sync_playwright() as p:

    browser = p.chromium.connect_over_cdp(
        "http://127.0.0.1:9222"
    )

    context = browser.contexts[0]

    # =================================================
    # HANDLE DETACHED PAGE ISSUE
    # =================================================

    if len(context.pages) > 0:

        page = context.pages[0]

    else:

        page = context.new_page()

    print("\nCONNECTED TO CHROME")

    # =================================================
    # OPEN PAGE SAFELY
    # =================================================

    try:

        page.goto(
            "https://vendorhub.flipkart.com/#/payments/invoices",
            timeout=120000
        )

    except:

        page = context.new_page()

        page.goto(
            "https://vendorhub.flipkart.com/#/payments/invoices",
            timeout=120000
        )

    time.sleep(4)

    rows = sheet.get_all_values()

    # =================================================
    # LOOP
    # =================================================

    for i in range(1, len(rows)):

        try:

            invoice = rows[i][2].strip()

            status = ""

            if len(rows[i]) >= 5:
                status = rows[i][4].strip()

            # =================================================
            # SKIP ONLY DONE
            # =================================================

            if status in ["DONE", "NOT FOUND"]:
                continue

            print(f"\nPROCESSING: {invoice}")

            tabs = [
                "Paid",
                "Approved For Payment",
                "In Process",
                "In Error"
            ]

            invoice_found = False

            pdf_link = None

            # =========================================
            # SEARCH ALL TABS
            # =========================================

            for tab in tabs:

                try:

                    print(f"CHECKING TAB: {tab}")

                    # CLICK TAB
                    page.get_by_text(tab).first.click(
                        force=True
                    )

                    time.sleep(2)

                    # =====================================
                    # SEARCH BOX
                    # =====================================

                    search_box = page.locator(
                        "input[placeholder*='Invoice']"
                    ).first

                    search_box.click()

                    page.keyboard.press("Control+A")

                    page.keyboard.press("Backspace")

                    time.sleep(0.5)

                    # TYPE INVOICE
                    search_box.fill(invoice)

                    print("INVOICE TYPED")

                    time.sleep(1)

                    # =====================================
                    # CLICK SEARCH TYPE
                    # =====================================

                    try:

                        page.get_by_text(
                            "Search by : Invoice ID",
                            exact=True
                        ).click(force=True)

                        print("SEARCH TYPE SELECTED")

                        time.sleep(1)

                    except Exception as e:

                        print("SEARCH TYPE FAILED")

                        print(e)

                    # =====================================
                    # PRESS ENTER
                    # =====================================

                    page.keyboard.press("Enter")

                    print("SEARCHED")

                    time.sleep(3)

                    # =====================================
                    # CHECK INVOICE
                    # =====================================

                    if page.locator(
                        f"text={invoice}"
                    ).count() > 0:

                        invoice_found = True

                        print(f"FOUND IN TAB: {tab}")

                        # =================================
                        # CLICK 3 DOT MENU
                        # =================================

                        menu_button = page.locator(
                            "svg.styles__More-sc-1r4phtv-0"
                        ).first

                        menu_button.scroll_into_view_if_needed()

                        time.sleep(1)

                        menu_button.click(force=True)

                        print("MENU OPENED")

                        time.sleep(1)

                        # =================================
                        # GET REAL PDF LINK
                        # =================================

                        links = page.evaluate("""
                        () => {
                            return Array.from(
                                document.querySelectorAll('a')
                            )
                            .map(a => ({
                                text: a.innerText,
                                href: a.href
                            }))
                            .filter(x => x.href);
                        }
                        """)

                        for link in links:

                            href = link["href"]

                            if (
                                "/document/INVOICE/" in href
                                and "/download" in href
                            ):

                                pdf_link = href

                                break

                        if not pdf_link:

                            raise Exception(
                                "PDF LINK NOT FOUND"
                            )

                        print("PDF LINK:", pdf_link)

                        break

                    else:

                        print(
                            f"NOT FOUND IN TAB: {tab}"
                        )

                except Exception as e:

                    print(f"TAB ERROR: {tab}")

                    print(e)

            # =========================================
            # NOT FOUND
            # =========================================

            if not invoice_found:

                print("NOT FOUND")

                sheet.update(
                    range_name="E" + str(i + 1),
                    values=[["NOT FOUND"]]
                )

                continue

            # =========================================
            # DOWNLOAD PDF
            # =========================================

            response = page.context.request.get(
                pdf_link,
                timeout=180000
            )

            final_pdf = os.path.join(
                DOWNLOAD_PATH,
                f"{invoice}.pdf"
            )

            with open(final_pdf, "wb") as f:

                f.write(response.body())

            print("DOWNLOADED")

            # =========================================
            # FILE SIZE INFO ONLY
            # =========================================

            file_size = os.path.getsize(
                final_pdf
            )

            print(f"FILE SIZE: {file_size}")

            # =========================================
            # UPLOAD TO GOOGLE DRIVE
            # =========================================

            file_metadata = {
                "name": f"{invoice}.pdf",
                "parents": [FOLDER_ID]
            }

            media = MediaFileUpload(
                final_pdf,
                mimetype="application/pdf"
            )

            uploaded = False

            for attempt in range(3):

                try:

                    drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields="id"
                    ).execute()

                    uploaded = True

                    print("UPLOADED TO DRIVE")

                    break

                except Exception as e:

                    print(
                        f"UPLOAD RETRY {attempt + 1}"
                    )

                    print(e)

                    time.sleep(5)

            if not uploaded:

                raise Exception(
                    "GOOGLE DRIVE UPLOAD FAILED"
                )

            # =========================================
            # UPDATE SHEET
            # =========================================

            sheet.update(
                range_name="E" + str(i + 1),
                values=[["DONE"]]
            )

            print("SHEET UPDATED")

            # =========================================
            # GO BACK
            # =========================================

            page.go_back()

            time.sleep(2)

        except Exception as e:

            print(f"FAILED: {invoice}")

            print(e)

            try:

                sheet.update(
                    range_name="E" + str(i + 1),
                    values=[["FAILED"]]
                )

            except:
                pass

            continue

    print("\nALL COMPLETED")