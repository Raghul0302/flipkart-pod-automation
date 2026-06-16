# Flipkart POD Automation

## What This Project Does
Automates the process of downloading invoices from Flipkart VendorHub 
and uploading them to Google Drive and internal logistics system.

## Tech Stack
- Python
- Playwright (Browser Automation)
- Google Sheets API
- Google Drive API
- Requests

## Features
- Auto logs into Flipkart VendorHub
- Searches invoices across multiple tabs (Paid, Approved, In Process, In Error)
- Downloads invoice PDFs automatically
- Uploads to Google Drive
- Updates Google Sheet status (DONE / NOT FOUND / FAILED)
- Converts PDF to images and uploads to logistics API

## Impact
- Reduced manual invoice processing time by 90%
- Processes hundreds of invoices automatically
- Zero manual intervention needed after setup
