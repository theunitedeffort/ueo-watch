#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import logging
import os
import re

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import pandas as pd
import requests
import yaml

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(encoding='utf-8', level=logging.DEBUG)

# Google Drive API setup
scope = ['https://www.googleapis.com/auth/drive']
service_account_json_key = os.environ['SERVICE_ACCOUNT_CREDENTIAL_FILE']
credentials = service_account.Credentials.from_service_account_file(
    filename=service_account_json_key,
    scopes=scope
)
service = build('drive', 'v3', credentials=credentials)

csv_bytes = service.files().export_media(fileId="1eRDtHWCFHYPDJQv_QCeqGUmPQJsdv-aQAnGfK8LnMfU", mimeType='text/csv').execute()
# The loaded CSV should always be relatively small (~100 lines) so we can just
# load it into pandas directly from memory.
df = pd.read_csv(io.BytesIO(csv_bytes), keep_default_na=False)

# Base URL for the housing data
# Include client ID in case there are two clients with exactly the same search
# params--outputted URLs must be unique for urlwatch.
base_url = 'https://www.theunitedeffort.org/data/housing/affordable-housing/filter'

# Function to create URLs based on client data
def generate_urls(df):
  urls = []
  processed_ids = []
  for _, row in df.iterrows():
    logger.info(f'\nProcessing row: {row.to_dict()}')
    if 'Affordable Housing' not in row['Housing Options']:
      logger.info('Affordable housing not specified as a housing option. Skipping.')
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

    logger.debug(f'Raw rent string: {row['Monthly Rent Budget']}')
    # Blow away dates in case the year is interpreted as a rent value
    rent_max = re.sub(r'(\d{4}|\d{1,2})[/\-]\d{1,2}[/\-](\d{4}|\d{1,2})',
      '[date]', row['Monthly Rent Budget'])
    # Numbers may be written as e.g. "1K" so replace that with "1,000"
    rent_max = re.sub(r'(\d)K', r'\1,000', rent_max)
    # Get 3 or 4 digit numbers and strip out any comma separators
    rent_matches = [int(m.replace(',', '')) for m in re.findall(r'\d?,?\d{3,4}', rent_max)]
    if rent_matches:
      params['rentMax'] = max(rent_matches)
      logger.debug(f'parsed max rent: {params['rentMax']}')
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
    urls.append({'name': f'Client ID {client_id}', 'url': req.url})
  return urls

# Generate URLs and save to a YAML file
urls = generate_urls(df)

with open('urls.yaml', 'w') as file:
  yaml.dump_all(urls, file)
