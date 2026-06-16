# Flipkart POD Automation

## What This Project Does
Automates the complete POD (Proof of Delivery) workflow in a single script:
1. Reads Invoice IDs and SOIDs from Google Sheet
2. Logs into Flipkart VendorHub and searches each invoice
3. Downloads the invoice PDF automatically
4. Converts PDF to images and compresses them
5. Uploads to Ninjacart logistics backend API
6. Updates Google Sheet status as DONE / FAILED / NOT FOUND

## Tech Stack
- Python
- Playwright (Browser Automation)
- Google Sheets API
- PyMuPDF (PDF to Image conversion)
- Pillow (Image compression)
- Requests (REST API)

## How It Works
- Skips already DONE and NOT FOUND invoices
- Retries failed uploads up to 5 times
- Deletes local PDF after successful upload
- Zero manual intervention after setup

## Impact
- Reduced manual POD processing time by 90%
- Handles hundreds of invoices automatically
- Eliminated need for Google Drive as intermediate storage
