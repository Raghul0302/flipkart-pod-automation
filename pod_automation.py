import os
import time
import gspread
import requests
import fitz  # PyMuPDF
from PIL import Image
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
from requests.auth import HTTPBasicAuth

# =====================================================
# IMPORTANT — BEFORE RUNNING:
#
# 1. Open separate automation Chrome:
#
# "C:\Program Files\Google\Chrome\Application\chrome.exe"
# --remote-debugging-port=9222
# --user-data-dir="C:\flipkart_pod_automation\chrome_profile"
#
# 2. Login to Flipkart VendorHub
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
#       python pod_automation.py
# =====================================================

# =====================================================
# CONFIG
# =====================================================

BASE_PATH     = r"C:\flipkart_pod_automation"
DOWNLOAD_PATH = os.path.join(BASE_PATH, "downloads")

os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# =====================================================
# NINJACART API
# =====================================================

API_URL  = "http://logistics.ninjacart.in/asgard/blink/tripRouteMapDetails/capture/invoice/SO"
USERNAME = "NC23761"
PASSWORD = "Ranga@2026"

# =====================================================
# GOOGLE SHEET
# =====================================================
# Sheet columns:
#   A → TripDate
#   B → City
#   C → InvoiceID
#   D → Remarks
#   E → Status   (DONE / FAILED / NOT FOUND)
#   F → SOID
# =====================================================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    os.path.join(BASE_PATH, "credentials.json"),
    scope
)

client = gspread.authorize(creds)

sheet = client.open(
    "January- May4 POD pending cases"
).worksheet("Main")

print("✅ Google Sheet Connected")

# =====================================================
# HELPER — CONVERT PDF TO IMAGES
# =====================================================

def convert_pdf_to_images(pdf_path):

    images = []

    try:

        doc = fitz.open(pdf_path)

        for i in range(len(doc)):

            page = doc.load_page(i)

            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))

            img = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            images.append(img)

        doc.close()

    except Exception as e:

        print(f"❌ PDF Conversion Error: {e}")

    return images

# =====================================================
# HELPER — COMPRESS IMAGE
# =====================================================

def compress_image(img, output_path):

    try:

        img = img.convert("RGB")

        img.save(
            output_path,
            "JPEG",
            quality=50,
            optimize=True
        )

        return True

    except Exception as e:

        print(f"❌ Compression Error: {e}")

        return False

# =====================================================
# HELPER — UPLOAD IMAGE TO NINJACART API
# =====================================================

def upload_image(image_path, image_name, soid, delete_existing=False):

    if delete_existing:
        url = f"{API_URL}?deleteExisting=true&saleOrderId={soid}"
    else:
        url = f"{API_URL}?saleOrderId={soid}"

    for attempt in range(5):

        try:

            with open(image_path, 'rb') as img_file:

                files = {
                    'invoiceImage': (
                        image_name,
                        img_file,
                        'image/jpeg'
                    )
                }

                response = requests.post(
                    url,
                    files=files,
                    auth=HTTPBasicAuth(USERNAME, PASSWORD),
                    timeout=120
                )

            print(f"   [UPLOAD] {image_name} → {response.status_code}")

            if response.status_code == 200:
                print("   ✅ Upload Success")
                return True
            else:
                print(f"   ❌ Upload Failed: {response.text}")

        except Exception as e:

            print(f"   [RETRY {attempt + 1}] {e}")
            time.sleep(5)

    return False

# =====================================================
# HELPER — PROCESS PDF AND UPLOAD ALL PAGES
# =====================================================

def process_and_upload(pdf_path, invoice_id, soid):

    images = convert_pdf_to_images(pdf_path)

    if not images:
        print("   ❌ No images extracted from PDF")
        return False

    success = True

    for i, image in enumerate(images):

        temp_path = os.path.join(
            DOWNLOAD_PATH,
            f"temp_{invoice_id}_{i + 1}.jpg"
        )

        compressed_path = os.path.join(
            DOWNLOAD_PATH,
            f"compressed_{invoice_id}_{i + 1}.jpg"
        )

        try:

            image.save(temp_path)

            if not compress_image(Image.open(temp_path), compressed_path):
                success = False
                break

            # First page → delete existing in backend
            if i == 0:
                uploaded = upload_image(
                    compressed_path,
                    f"{invoice_id}_{i + 1}.jpg",
                    soid,
                    delete_existing=True
                )
            else:
                uploaded = upload_image(
                    compressed_path,
                    f"{invoice_id}_{i + 1}.jpg",
                    soid
                )

            if not uploaded:
                success = False
                break

        except Exception as e:

            print(f"   ❌ Page {i + 1} Error: {e}")
            success = False
            break

        finally:

            # Cleanup temp files
            if os.path.exists(temp_path):
                os.remove(temp_path)

            if os.path.exists(compressed_path):
                os.remove(compressed_path)

    return success

# =====================================================
# MAIN
# =====================================================

with sync_playwright() as p:

    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")

    context = browser.contexts[0]

    page = context.pages[0]

    print("✅ Connected to Chrome\n")

    # Open Flipkart Invoices Page once
    page.goto(
        "https://vendorhub.flipkart.com/#/payments/invoices",
        timeout=120000
    )

    time.sleep(4)

    rows = sheet.get_all_values()

    tabs = ["Paid", "Approved For Payment", "In Process", "In Error"]

    # =================================================
    # LOOP THROUGH EACH ROW IN SHEET
    # =================================================

    for i in range(1, len(rows)):

        invoice = ""

        try:

            row_data = rows[i]

            # Skip empty rows
            if len(row_data) < 3 or not row_data[2].strip():
                continue

            invoice = row_data[2].strip()                                        # Column C - InvoiceID
            status  = row_data[4].strip() if len(row_data) >= 5 else ""         # Column E - Status
            soid    = row_data[5].strip() if len(row_data) >= 6 else ""         # Column F - SOID

            # -----------------------------------------
            # SKIP DONE AND NOT FOUND
            # -----------------------------------------

            if status in ["DONE", "NOT FOUND"]:
                print(f"⏭️  Skipping {invoice} → {status}")
                continue

            print(f"===================================")
            print(f"📄 Invoice : {invoice}")
            print(f"🔗 SOID    : {soid}")
            print(f"===================================")

            # -----------------------------------------
            # VALIDATE SOID
            # -----------------------------------------

            if not soid:
                print(f"⚠️  No SOID found for {invoice} — marking FAILED")
                sheet.update_cell(i + 1, 5, "FAILED")
                continue

            invoice_found = False
            pdf_link      = None

            # -----------------------------------------
            # SEARCH ACROSS ALL TABS
            # -----------------------------------------

            for tab in tabs:

                try:

                    print(f"   Checking tab: {tab}")

                    page.get_by_text(tab).first.click(force=True)
                    time.sleep(2)

                    # Type in search box
                    search_box = page.locator(
                        "input[placeholder*='Invoice']"
                    ).first

                    search_box.click()
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    time.sleep(0.5)

                    search_box.fill(invoice)
                    time.sleep(1)

                    # Select search type
                    try:
                        page.get_by_text(
                            "Search by : Invoice ID",
                            exact=True
                        ).click(force=True)
                        time.sleep(1)
                    except:
                        pass

                    page.keyboard.press("Enter")
                    time.sleep(3)

                    # Check if invoice appears
                    if page.locator(f"text={invoice}").count() > 0:

                        invoice_found = True
                        print(f"   ✅ Found in tab: {tab}")

                        # Open 3 dot menu
                        menu_button = page.locator(
                            "svg.styles__More-sc-1r4phtv-0"
                        ).first

                        menu_button.scroll_into_view_if_needed()
                        time.sleep(1)
                        menu_button.click(force=True)
                        time.sleep(1)

                        # Get PDF download link
                        links = page.evaluate("""
                            () => Array.from(document.querySelectorAll('a'))
                                .map(a => ({ text: a.innerText, href: a.href }))
                                .filter(x => x.href)
                        """)

                        for link in links:
                            href = link["href"]
                            if "/document/INVOICE/" in href and "/download" in href:
                                pdf_link = href
                                break

                        if not pdf_link:
                            raise Exception("PDF link not found in menu")

                        print(f"   🔗 PDF Link found")
                        break

                    else:
                        print(f"   ✖ Not in tab: {tab}")

                except Exception as e:
                    print(f"   ⚠️  Tab error ({tab}): {e}")

            # -----------------------------------------
            # NOT FOUND IN ANY TAB
            # -----------------------------------------

            if not invoice_found:
                print(f"❌ NOT FOUND: {invoice}")
                sheet.update_cell(i + 1, 5, "NOT FOUND")
                continue

            # -----------------------------------------
            # DOWNLOAD PDF
            # -----------------------------------------

            response = page.context.request.get(pdf_link)

            pdf_path = os.path.join(DOWNLOAD_PATH, f"{invoice}.pdf")

            with open(pdf_path, "wb") as f:
                f.write(response.body())

            file_size = os.path.getsize(pdf_path)
            print(f"   📥 Downloaded — {file_size} bytes")

            if file_size < 15000:
                raise Exception("Invalid PDF — file too small")

            # -----------------------------------------
            # CONVERT & UPLOAD TO NINJACART API
            # -----------------------------------------

            success = process_and_upload(pdf_path, invoice, soid)

            # -----------------------------------------
            # DELETE LOCAL PDF
            # -----------------------------------------

            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                print("   🗑️  Local PDF deleted")

            # -----------------------------------------
            # UPDATE SHEET STATUS
            # -----------------------------------------

            if success:
                sheet.update_cell(i + 1, 5, "DONE")
                print(f"✅ DONE: {invoice}\n")
            else:
                sheet.update_cell(i + 1, 5, "FAILED")
                print(f"❌ FAILED: {invoice}\n")

            page.go_back()
            time.sleep(2)

        except Exception as e:

            print(f"❌ ERROR: {invoice} → {e}")

            try:
                sheet.update_cell(i + 1, 5, "FAILED")
            except:
                pass

            # Cleanup any leftover PDF
            try:
                pdf_path = os.path.join(DOWNLOAD_PATH, f"{invoice}.pdf")
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except:
                pass

            continue

print("\n🎉 ALL DONE")
