from datetime import datetime
import os
# NetFree SSL fix
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
os.environ['SSL_CERT_FILE'] = '/etc/ssl/certs/ca-certificates.crt'
# os.environ['SSL_CERT_FILE'] = certifi.where()

import certifi
import re
import io
import time
import argparse
import subprocess
import logging

from pyairtable import Table
from pyairtable import Api
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# import ssl
# context = ssl._create_unverified_context()

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(message)s"
# )
logger = logging.getLogger(__name__)

def get_folder_id_from_url(url):
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None

def download_spreadsheets(folder_id, drive_service, output_dir="downloads"):
    query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet'"
    files = drive_service.files().list(q=query, fields="files(id, name)").execute().get('files', [])
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    downloaded_files = []
    for file in files:
        file_id = file['id']
        file_name = file['name'] + '.xlsx'
        path = os.path.join(output_dir, file_name)
        request = drive_service.files().export_media(
            fileId=file_id,
            mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        with open(path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        logger.info(f"Downloaded: {file_name}")
        downloaded_files.append(path)
    return downloaded_files

def convert_and_print(file_path, printer) -> bool:
    try:
        subprocess.run([
            "libreoffice", "--headless", "--convert-to", "pdf", file_path, "--outdir", "/tmp"
        ], check=True)
        pdf_path = "/tmp/" + os.path.basename(file_path).replace('.xlsx', '.pdf')
        subprocess.run(["lpr", "-P", printer, pdf_path], check=True)
        logger.info(f"Printed: {pdf_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error printing {file_path}: {e}")
        return False

    return True

def process_records(table, drive_service, printer):
    records = table.all(formula="NOT({הודפס})")
    for record in records:
        fields = record.get('fields', {})
        record_id = record['id']
        folder_url = fields.get("18. קישור לתיקיית הזמנה")
        if folder_url:
            folder_id = get_folder_id_from_url(folder_url)
            if folder_id:
                logger.info(f"Processing record: {record_id}")
                files = download_spreadsheets(folder_id, drive_service)
                for f in files:
                    if convert_and_print(f, printer) == True:
                        table.update(record_id, {"הודפס": True})
                        logger.info("Marked as printed.\n")
                    else:
                        logger.error(f"Failed to print {f}.")
                        exit (1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--table', required=True)
    parser.add_argument('--printer', required=True)
    parser.add_argument('--interval', type=int, default=5)
    parser.add_argument('--creds', default='service_account.json')
    args = parser.parse_args()

    # table = Table(args.token, args.base, args.table)
    api = Api(args.token)
    table = api.table(args.base, args.table)    
    creds = service_account.Credentials.from_service_account_file(
        args.creds, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    drive_service = build('drive', 'v3', credentials=creds)

    while True:
        logger.info("Checking for new unprinted records...")
        try:
            process_records(table, drive_service, args.printer)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        night_more_interval = 1
        now = datetime.now().hour
        if now < 9 or now > 23:
            logger.info("Outside of printing hours (9 AM - 11 PM). Waiting for next interval.")
            night_more_interval = 10

        sleep_time = args.interval * 60 * night_more_interval
        logger.info(f"Sleeping for {sleep_time/60} minutes...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    # Ensure logs directory exists
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Set up logging to file and console
    log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler("logs/printer_bot.log", encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)

    #logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear existing handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(" ")
    logger.info("------------------------------------------------------")
    logger.info(f"Starting printer bot at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("------------------------------------------------------")

    main()
