#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import logging
import os
import re
import subprocess

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import pandas as pd
import requests
import yaml

OUTPUT_FILENAME = 'urls.yaml'  # Relative to this script's location.
CACHE_FILENAME = 'cache.db'  # Relative to this script's location.
GOOGLE_DRIVE_SRC_DIR_ID = '187ydaRH3bi-klu3G_GP66gIMt6j0zHI6'

MIME_GOOGLE_SHEETS = 'application/vnd.google-apps.spreadsheet'
MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
MIME_XLS = 'application/vnd.ms-excel'
MIME_CSV = 'text/csv'

SUPPORTED_MIME_TYPES = [
  MIME_GOOGLE_SHEETS,
  MIME_XLS,
  MIME_XLSX,
  MIME_CSV
]

def read_csv(csv_bytes):
  return pd.read_csv(io.BytesIO(csv_bytes), keep_default_na=False, dtype='string')

def read_excel(excel_bytes):
  return pd.read_excel(io.BytesIO(excel_bytes), keep_default_na=False, dtype='string')

def get_sheet_as_csv_bytes(drive_api, file_metadata):
  return drive_api.files().export_media(fileId=file_metadata['id'], mimeType=MIME_CSV).execute()

def get_file_bytes(drive_api, file_metadata):
  return drive_api.files().get_media(fileId=file_metadata['id']).execute()


load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(encoding='utf-8', level=logging.DEBUG)

local_dir = os.path.dirname(__file__)
output_path = os.path.join(local_dir, OUTPUT_FILENAME)
logger.debug(f'Output file path is {output_path}')

# Google Drive API setup
scope = ['https://www.googleapis.com/auth/drive']
service_account_json_key = os.environ['SERVICE_ACCOUNT_CREDENTIAL_FILE']
credentials = service_account.Credentials.from_service_account_file(
    filename=service_account_json_key,
    scopes=scope
)
service = build('drive', 'v3', credentials=credentials)

# Call the Drive v3 API
results = service.files().list(
  q=f"'{GOOGLE_DRIVE_SRC_DIR_ID}' in parents and trashed = false",
  orderBy='modifiedTime desc',
  includeItemsFromAllDrives=True,
  supportsAllDrives=True,
  pageSize=100,
  fields="files(id, name, mimeType, modifiedTime)").execute()
items = results.get('files', [])
src_file = None
# Files are sorted from most recent to oldest, so grab the first (most recent)
# supported file.
for item in items:
  if item['mimeType'] not in SUPPORTED_MIME_TYPES:
    logger.info(f'Unsupported MIME type: {item} Skipping file.')
    continue
  src_file = item
  logger.info(f'Using source file: {src_file}')
  break

if not src_file:
  raise ValueError('No suitable source file found.')

df = pd.DataFrame([])
# The loaded file should always be relatively small (~100 lines) so we can just
# load it into pandas directly from memory rather than saving it to disk first.
if src_file['mimeType'] == MIME_GOOGLE_SHEETS:
  df = read_csv(get_sheet_as_csv_bytes(service, src_file))
elif src_file['mimeType'] == MIME_CSV:
  df = read_csv(get_file_bytes(service, src_file))
elif src_file['mimeType'] in [MIME_XLS, MIME_XLSX]:
  df = read_excel(get_file_bytes(service, src_file))

# Base URL for the housing data
# Include client ID in case there are two clients with exactly the same search
# params--outputted URLs must be unique for urlwatch.
base_url = 'https://www.theunitedeffort.org/data/housing/affordable-housing/filter'

# Function to create URLs based on client data
def generate_jobs(df):
  jobs = {}
  processed_ids = []
  for _, row in df.iterrows():
    logger.info(f'\nProcessing row: {row.to_dict()}')
    allowlist = ['Affordable Housing', 'Market Rate Apartment']
    if all(v not in row['Housing Options'] for v in allowlist):
      logger.info(
        f"Housing options do not contain {', '.join(allowlist)}. Skipping.")
      continue
    # There is nothing to prevent duplicate housing plans in our client
    # management system, so just grab the first one here until there is
    # a better way to choose a 'best' one from a set of entries.
    client_id = row['Record ID']
    if client_id in processed_ids:
      logger.warn(f'Client {client_id} already processed. Skipping duplicate entry.')
      continue
    processed_ids.append(client_id)

    url = f'{base_url}#{client_id}'
    params = {}

    params['availability'] = ['Available', 'Waitlist Open']

    params['city'] = row['Location Preferences'].split('|')

    logger.debug(f"Raw rent string: {row['Monthly Rent Budget']}")
    # Blow away dates in case the year is interpreted as a rent value
    rent_max = re.sub(r'(\d{4}|\d{1,2})[/\-]\d{1,2}[/\-](\d{4}|\d{1,2})',
      '[date]', row['Monthly Rent Budget'])
    # Numbers may be written as e.g. "1K" so replace that with "1,000"
    rent_max = re.sub(r'(\d)K', r'\1,000', rent_max)
    # Get 3 or 4 digit numbers and strip out any comma separators
    rent_matches = [int(m.replace(',', '')) for m in re.findall(r'\d?,?\d{3,4}', rent_max)]
    if rent_matches:
      params['rentMax'] = max(rent_matches)
      logger.debug(f"parsed max rent: {params['rentMax']}")
    else:
      logger.debug('no max rent found')
    params['includeUnknownRent'] = 'on'

    # Since we only record age in our housing preferences, include all
    # other populations by default and only add in Senior or Youth when
    # relevant.  If we start recording disability or veteran status in
    # housing preferences, then those can instead be conditionally added.
    params['populationsServed'] = [
      'General Population',
      'Developmentally Disabled',
      'Physically Disabled',
      'Veterans'
    ]
    if row['Age']:
      age = None
      try:
       age = int(row['Age'])
      except ValueError:
        pass
      if age and age >= 55:
        params['populationsServed'].append('Seniors')
      if age and age <= 18:
        params['populationsServed'].append('Youth')

    logger.info(f'final query parameters: {params}')
    req = requests.PreparedRequest()
    req.prepare_url(url, params)
    jobs[client_id] = {
      'kind': 'url',
      'name': f'Client ID {client_id}',
      'id': client_id,  # Not a urlwatch prop, but useful for our script here.
      'url': req.url,
      # The user visible URL is not the json data feed, but rather the regular
      # housing search interface.  Note this is the URL that the urlwatch
      # database uses as a key.
      'user_visible_url': req.url.replace('/data/', '/')
    }
  return jobs

# Generate URLs and save to a YAML file
jobs = generate_jobs(df)

# It's possible that a client's search preferences will change over time.  When
# they do, a new search URL will be generated since all preferences are stored
# in the URL.  To keep the historical snapshots consistent, the URL needs
# to be updated in the urlwatch history database.
cache_path = os.path.join(local_dir, CACHE_FILENAME)
if os.path.exists(output_path) and os.path.exists(cache_path):
  # Only need to check for conflicts if there is already a urls.yaml and a
  # historical database existing.
  with open(output_path, 'r') as file:
    old_jobs = list(yaml.safe_load_all(file))
  for old_job in old_jobs:
    client_id = old_job['id']
    if client_id in jobs:
      old_url = old_job['user_visible_url']
      new_url = jobs[client_id]['user_visible_url']
      if old_url != new_url:
        # The client exists in both the new list of URLs and the old one, but
        # the URLs themselves do not match.
        logger.info(f"URL for client ID {client_id} needs updating "
          f"from {old_url} to {new_url}")
        command = [
          'urlwatch',
          '--urls', output_path,
          '--cache', cache_path,
          '--change-location', old_url, new_url
        ]
        logger.debug(f"running command: {' '.join(command)}")
        subprocess.run(command)

if not jobs:
  raise ValueError('No jobs to write!  Is the source file formatted correctly?')

logger.info(f'Writing {len(jobs)} URLs to {output_path}')
with open(output_path, 'w') as file:
  yaml.dump_all(jobs.values(), file)
logger.info('All finished!  Goodbye.')