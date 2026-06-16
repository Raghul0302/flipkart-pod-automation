# Flipkart POD Automation

## What This Project Does
Automates the complete POD (Proof of Delivery) workflow:
1. Downloads invoices from Flipkart VendorHub
2. Uploads them to internal logistics API as images

## Tech Stack
- Python
- Playwright (Browser Automation)
- Google Sheets API
- Google Drive API
- PyMuPDF (PDF to Image conversion)
- Pillow (Image compression)
- Requests (REST API)

## Scripts
- `main.py` → Downloads invoices from Flipkart VendorHub to Google Drive
- `upload.py` → Downloads from Drive, converts PDF to image, uploads to logistics API

## Features
- Auto searches invoices across multiple tabs on VendorHub
- Downloads invoice PDFs automatically
- Converts PDF pages to compressed images
- Uploads to Ninjacart logistics backend API
- Updates Google Sheet status in real time
- Skips already processed files automatically

## Impact
- Reduced manual POD processing time by 90%
- Handles hundreds of invoices automatically
- Zero manual intervention needed after setup
