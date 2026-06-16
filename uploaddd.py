import os
import io
import time
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
from PIL import Image
import fitz  # PyMuPDF

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# =========================================================
# CONFIG
# =========================================================

SCOPES = ['https://www.googleapis.com/auth/drive']

BASE_PATH = r"C:\invoice_automation"

EXCEL_PATH = os.path.join(BASE_PATH, "data.xlsx")

# GOOGLE DRIVE FOLDER ID
FOLDER_ID = "1TEQ6bET8n2GdzBMF_Aofs5oMWekkA8bG"

# =========================================================
# API DETAILS
# =========================================================

BASE_URL = "http://logistics.ninjacart.in/asgard/blink/tripRouteMapDetails/capture/invoice/SO"

USERNAME = "NC26115"
PASSWORD = "Ragh@1234"

# =========================================================
# GOOGLE DRIVE AUTH
# =========================================================

creds = Credentials.from_authorized_user_file(
    os.path.join(BASE_PATH, "token.json"),
    SCOPES
)

drive_service = build('drive', 'v3', credentials=creds)

# =========================================================
# READ EXCEL
# =========================================================

df = pd.read_excel(EXCEL_PATH)

df['InvoiceID'] = df['InvoiceID'].astype(str).str.strip()
df['SOID'] = df['SOID'].astype(str).str.strip()

print("✅ Excel Loaded")

# =========================================================
# DOWNLOAD FILE FROM DRIVE
# =========================================================

def download_file(file_id, filepath):

    request = drive_service.files().get_media(fileId=file_id)

    fh = io.BytesIO()

    downloader = MediaIoBaseDownload(fh, request)

    done = False

    while not done:

        status, done = downloader.next_chunk()

    fh.seek(0)

    with open(filepath, 'wb') as f:

        f.write(fh.read())

# =========================================================
# RENAME DONE FILE
# =========================================================

def mark_as_done(file_id, filename):

    try:

        new_name = "DONE_" + filename

        drive_service.files().update(
            fileId=file_id,
            body={"name": new_name},
            supportsAllDrives=True
        ).execute()

        print(f"✅ Renamed → {new_name}")

        return True

    except Exception as e:

        print(f"❌ Rename Error: {e}")

        return False

# =========================================================
# PDF TO IMAGES
# =========================================================

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

# =========================================================
# COMPRESS IMAGE
# =========================================================

def compress_image(input_path, output_path):

    try:

        img = Image.open(input_path)

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

# =========================================================
# UPLOAD IMAGE
# =========================================================

def upload_image(image_path, image_name, soid, delete_existing=False):

    if delete_existing:
        url = f"{BASE_URL}?deleteExisting=true&saleOrderId={soid}"
    else:
        url = f"{BASE_URL}?saleOrderId={soid}"

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

            print(f"[UPLOAD] {image_name} → {response.status_code}")

            if response.status_code == 200:

                print("✅ Upload Success")

                return True

            else:

                print(f"❌ Upload Failed: {response.text}")

        except Exception as e:

            print(f"[RETRY {attempt+1}] {e}")

            time.sleep(5)

    return False

# =========================================================
# GET ALL FILES FROM DRIVE (FIXED)
# =========================================================

files = []
page_token = None

while True:

    try:

        results = drive_service.files().list(
            q=f"'{FOLDER_ID}' in parents and trashed=false",
            fields="nextPageToken, files(id,name,mimeType)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        batch_files = results.get('files', [])

        files.extend(batch_files)

        print(f"Fetched {len(batch_files)} files")

        page_token = results.get('nextPageToken')

        if not page_token:
            break

    except Exception as e:

        print(f"❌ Drive Fetch Error: {e}")

        time.sleep(5)

if not files:

    print("⚠️ No files found in Drive")
    exit()

print(f"\n✅ TOTAL FILES FOUND: {len(files)}")

# =========================================================
# MAIN PROCESS
# =========================================================

for index, file in enumerate(files, start=1):

    try:

        file_id = file['id']
        filename = file['name']
        mime_type = file['mimeType']

        print("\n=================================================")
        print(f"[{index}/{len(files)}] PROCESSING: {filename}")
        print("=================================================")

        # SKIP DONE FILES
        if filename.startswith("DONE_"):

            print(f"⏭️ Skipped DONE File")

            continue

        # REMOVE EXTENSION
        invoice_id = os.path.splitext(filename)[0]

        # KEEP ONLY NUMBERS
        invoice_id = ''.join(filter(str.isdigit, invoice_id))

        if not invoice_id:

            print(f"❌ Invalid filename")

            continue

        print(f"Invoice ID: {invoice_id}")

        # FIND SOID
        row = df[df['InvoiceID'] == invoice_id]

        if row.empty:

            print("❌ Invoice ID not found in Excel")

            continue

        soid = str(row.iloc[0]['SOID']).strip()

        print(f"SOID Found: {soid}")

        # LOCAL FILE PATH
        local_file = os.path.join(BASE_PATH, filename)

        # DELETE OLD FILE IF EXISTS
        if os.path.exists(local_file):

            try:
                os.remove(local_file)
            except:
                pass

        # DOWNLOAD FILE
        try:

            download_file(file_id, local_file)

            print("✅ File Downloaded")

        except Exception as e:

            print(f"❌ Download Failed: {e}")

            continue

        success = False

        # =====================================================
        # IMAGE FILE
        # =====================================================

        if mime_type.startswith("image/"):

            compressed_path = os.path.join(
                BASE_PATH,
                f"compressed_{invoice_id}.jpg"
            )

            if compress_image(local_file, compressed_path):

                success = upload_image(
                    compressed_path,
                    f"{invoice_id}.jpg",
                    soid,
                    delete_existing=True
                )

            # DELETE COMPRESSED FILE
            if os.path.exists(compressed_path):

                try:
                    os.remove(compressed_path)
                except:
                    pass

        # =====================================================
        # PDF FILE
        # =====================================================

        elif mime_type == "application/pdf":

            images = convert_pdf_to_images(local_file)

            if not images:

                print("❌ PDF Conversion Failed")

                if os.path.exists(local_file):
                    os.remove(local_file)

                continue

            success = True

            for i, image in enumerate(images):

                temp_image = os.path.join(
                    BASE_PATH,
                    f"temp_{invoice_id}_{i+1}.jpg"
                )

                compressed_path = os.path.join(
                    BASE_PATH,
                    f"compressed_{invoice_id}_{i+1}.jpg"
                )

                try:

                    image.save(temp_image)

                    compressed = compress_image(
                        temp_image,
                        compressed_path
                    )

                    if not compressed:

                        success = False
                        break

                    # FIRST PAGE
                    if i == 0:

                        uploaded = upload_image(
                            compressed_path,
                            f"{invoice_id}_{i+1}.jpg",
                            soid,
                            delete_existing=True
                        )

                    # OTHER PAGES
                    else:

                        uploaded = upload_image(
                            compressed_path,
                            f"{invoice_id}_{i+1}.jpg",
                            soid
                        )

                    if not uploaded:

                        success = False
                        break

                except Exception as e:

                    print(f"❌ PDF Page Error: {e}")

                    success = False
                    break

                finally:

                    # DELETE TEMP FILES
                    if os.path.exists(temp_image):

                        try:
                            os.remove(temp_image)
                        except:
                            pass

                    if os.path.exists(compressed_path):

                        try:
                            os.remove(compressed_path)
                        except:
                            pass

        else:

            print(f"⚠️ Unsupported File Type: {mime_type}")

        # =====================================================
        # FINAL STATUS
        # =====================================================

        if success:

            renamed = mark_as_done(file_id, filename)

            if renamed:

                print("✅ COMPLETED SUCCESSFULLY")

            else:

                print("⚠️ Uploaded But Rename Failed")

        else:

            print("❌ FAILED")

        # DELETE LOCAL FILE
        if os.path.exists(local_file):

            try:
                os.remove(local_file)
            except:
                pass

        # SMALL DELAY
        time.sleep(1)

    except Exception as main_error:

        print(f"❌ MAIN LOOP ERROR: {main_error}")

        continue

print("\n🎉 ALL POD PROCESSING FINISHED")