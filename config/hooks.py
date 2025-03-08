import datetime
import json
import logging
import netrc
import os
import random
import re
import subprocess
import urllib.parse

from dotenv import load_dotenv
import requests
from urlwatch import filters
from urlwatch import jobs
from urlwatch import reporters
from urlwatch.mailer import SMTPMailer
from urlwatch.mailer import SendmailMailer

logger = logging.getLogger(__name__)
load_dotenv()

# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunkify(lst, n):
  """Yield n-sized chunks from the list 'lst'."""
  for i in range(0, len(lst), n):
      yield lst[i:i + n]


class ScraperJob(jobs.UrlJob):
  """Custom job to call Apify Super Scraper API"""

  __kind__ = 'scraper'

  __required__ = ('kind',)

  def retrieve(self, job_state):
    self.user_visible_url = self.url
    self.url = f'https://washed-ocelot--super-scraper-task.apify.actor?url={self.url}&transparent_status_code=true&render_js=false'
    self.headers = self.headers or {}
    auth_header = 'Authorization'
    existing_auth = [h for h in self.headers if h.lower() == auth_header.lower()]
    for header in existing_auth:
      self.headers.pop(header, None)
    apify_token = os.environ['APIFY_TOKEN']
    self.headers[auth_header] = f'Bearer {apify_token}'
    return super().retrieve(job_state)


class ErrorOnEmptyData(filters.FilterBase):
  __kind__ = 'if_empty'

  __supported_subfilters__ = {
    'action': 'What to do if the input data is empty [error, warn]',
  }

  __default_subfilter__ = 'action'

  def filter(self, data, subfilter):
    if subfilter['action'] not in ['error', 'warn']:
      raise ValueError('Invalid value for "action", must be "error" or "warn"')
    msg = 'Filter input is empty, no text to process.'
    if data.strip() == "":
      if subfilter['action'] == 'error':
        raise ValueError(msg)
      elif subfilter['action'] == 'warn':
        logger.warn(msg)
    return data


class SelectiveFilter(filters.FilterBase):
  __kind__ = 'selective'

  __supported_subfilters__ = {
    'filter': 'Name of the filter to be selectively applied',
    'select_pattern': 'List of patterns defining the selection',
    'invert_selection': 'Invert the selection made with select_pattern',
    '<any>': 'Subfilters associated with "filter"',
  }

  def filter(self, data, subfilter):
    if 'select_pattern' not in subfilter:
      raise ValueError('{} needs a select_pattern'.format(self.__kind__))
    subfilter['invert_selection'] = subfilter.get('invert_selection', False)
    select_pattern = subfilter['select_pattern']
    if not isinstance(select_pattern, list):
      select_pattern = [select_pattern]
    matched = any(re.match(p, self.job.get_location()) for p in select_pattern)
    do_process = not matched if subfilter['invert_selection'] else matched
    target_filter_kind = subfilter['filter']
    target_subfilter = dict(subfilter)
    for key in self.__supported_subfilters__:
      if key != '<any>':
        target_subfilter.pop(key)
    if not do_process:
      logger.info('Selectively skipping application of filter %r, subfilter %r to %s', target_filter_kind, target_subfilter, self.job.get_location())
      return data
    return filters.FilterBase.process(target_filter_kind, target_subfilter, self.state, data)

class EmailDecodeFilter(filters.FilterBase):
  __kind__ = 'decode_email'

  def filter(self, data, subfilter):
    def decode_scraper_shield(s):
      # https://gist.github.com/nullableVoidPtr/632583d4e34b4b1bf3b92f5b4f5d0c7d
      decoded = ""
      key = int(s[:2], 16)
      for char in [int(s[i:i+2], 16) for i in range(2, len(s), 2)]:
        decoded += chr(char ^ key)
      return decoded

    def decode_email(match):
      link = decode_scraper_shield(match.group(1))
      text = link
      # The linked address may be different than the displayed text (in rare
      # cases)
      match = re.search(r'data-cfemail=[\'"](.*?)[\'"]', match.group(0))
      if match:
        text = decode_scraper_shield(match.group(1))
      return '<a href="mailto:{link}">{text}</a>'.format(link=link, text=text)

    pattern = re.compile(r'<a[^<>]*?href=[\'"]/cdn-cgi/l/email-protection#([a-z0-9]+)[\'"][^<>]*?>.*?</a>',
      re.DOTALL)
    return re.sub(pattern, decode_email, data)


class ListingApiBase(filters.FilterBase):
  def filter(self, data, subfilter):
    filtered = filters.FilterBase.process('jq', {'query': self.__query__}, self.state, data)
    filtered = filters.FilterBase.process('remove-duplicate-lines', {}, self.state, filtered)
    filtered = filters.FilterBase.process('sort', {}, self.state, filtered)
    filtered = filters.FilterBase.process('re.sub', {'pattern': '"'}, self.state, filtered)
    filtered = filters.FilterBase.process('re.sub', {'pattern': r'\\n', 'repl': r'\n'}, self.state, filtered)
    return filtered


class RealPageUnits(ListingApiBase):
  """Filter for pretty-printing units JSON data from the realpage API."""

  __kind__ = 'realpage_units'
  __query__ = r'.response // . | .units[]? | "\(.numberOfBeds) BR\n---\n$\(.rent)/month\n\(.leaseStatus)\n\n"'


class RealPageFloorplans(ListingApiBase):
  """Filter for pretty-printing floorplan JSON data from the realpage API."""

  __kind__ = 'realpage_floorplans'
  __query__ = r'.response // . | .floorplans[]? | "\(.name)\n---\n\(.bedRooms) BR\n\(.rentType)\n\(.rentRange)\n\n"'


class AppFolioUnits(ListingApiBase):

  __kind__ = 'appfolio_units'
  __query__ = r'.values[]? | "\(.data.bedrooms) BR\n---\n$\(.data.market_rent | floor)/month\n\(.data.marketing_title)\navailable \(if "\(.data.available_date)T00:00:00Z" | fromdate < now then "now" else .data.available_date end)\n\n"'


class Apartments247Floorplans(ListingApiBase):

  __kind__ = 'apartments247_floorplans'
  __query__ = r'.[]? | "\(.name)\n---\n\(.bed) BR\n\(.rent)\n\n"'


class GraphqlUnits(ListingApiBase):

  __kind__ = 'graphql_units'
  __query__ = r'.data.apartmentComplex.apartments[] | "\(.floorplan.name)\n---\n\(.floorplan.beds) BR\n\(.prices[].formattedPrice)\n\n"'


class GraphqlFloorplans(ListingApiBase):

  __kind__ = 'graphql_floorplans'
  __query__ = r'.data.apartmentComplex.floorplans[] | "\(.name)\n---\n\(.beds) BR\n\(.rateDisplay // "")\n\(if .totalAvailableUnits > 0 then "\(.totalAvailableUnits) available units\n" else "" end)\(.floorplanCta.name // "")\n\n"'


class PrometheusAvailability(ListingApiBase):

  __kind__ = 'prometheus_avail'
  __query__ = r'group_by(.floorPlanName) | map(.[-1])[] | select(.floorPlanName | test("BMR")) | "\(.floorPlanName)\n---\n\(.bedrooms) BR\n$\(.bestRent)/month\n\n"'


class GcsFileReporter(reporters.HtmlReporter):
  """Custom reporter that writes an HTML file to Google Cloud Storage."""

  __kind__ = 'gcs'

  def submit(self):
    filename_args = {
      'datetime': self.report.start.strftime('%Y-%m-%d-%H%M%S'),
    }
    filename = self.config['filename'].format(**filename_args)
    local_dir = os.path.expanduser(self.config['local_dir'])
    if not os.path.exists(local_dir):
      os.makedirs(local_dir)
    local_path = os.path.join(local_dir, filename)
    with open(local_path, 'w') as file:
      for part in super().submit():
        file.write('%s\n' % part)
    logger.debug('Wrote %s', local_path)
    cmd = ['gsutil', 'cp', local_path, 'gs://%s' % (os.path.join(self.config['bucket'], self.config['gcs_dir']))]
    logger.debug('Calling %s', ' '.join(cmd))
    result = subprocess.run(cmd)
    if result.returncode == 0:
      logger.info('Upload successful, removing %s', local_path)
      os.remove(local_path)
    else:
      logger.error('Could not upload to Google Cloud Store.  The local file (%s) has not been removed.', local_path)


class CustomTextEmailReporter(reporters.TextReporter):
  """Custom reporter that sends a text email"""

  __kind__ = 'custom_email'

  def submit(self):
    filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))

    subject_args = {
      'count': len(filtered_job_states),
      'jobs': ', '.join(job_state.job.pretty_name() for job_state in filtered_job_states),
      'datetime': self.report.start.strftime('%b %d, %Y %I:%M:%S %p'),
    }
    subject = self.config['subject'].format(**subject_args)
    logger.debug(subject)
    body_text = '\n'.join(super().submit())

    if not body_text:
      logger.debug('Not sending e-mail (no changes)')
      return
    details_url_args = {
      'datetime': self.report.start.strftime('%Y-%m-%d-%H%M%S'),
    }
    details_url = self.config['details_url'].format(**details_url_args)
    body_sections = [
      'The following websites have changed.',
      'For details, visit %s' % details_url,
    ]
    tasks_url = self.config.get('tasks_url', '')
    if tasks_url:
      body_sections.append('To resolve these changes, visit %s' % tasks_url)
    body_sections.append(body_text)
    body_text = '\n\n'.join(body_sections)

    if self.config['method'] == "smtp":
      smtp_user = self.config['smtp'].get('user', None) or self.config['from']
      # Legacy support: The current smtp "auth" setting was previously called "keyring"
      if 'keyring' in self.config['smtp']:
        logger.info('The SMTP config key "keyring" is now called "auth". See https://urlwatch.readthedocs.io/en/latest/deprecated.html')
      use_auth = self.config['smtp'].get('auth', self.config['smtp'].get('keyring', False))
      mailer = SMTPMailer(smtp_user, self.config['smtp']['host'], self.config['smtp']['port'],
                self.config['smtp']['starttls'], use_auth,
                self.config['smtp'].get('insecure_password'))
    elif self.config['method'] == "sendmail":
      mailer = SendmailMailer(self.config['sendmail']['path'])
    else:
      logger.error('Invalid entry for method {method}'.format(method=self.config['method']))

    reply_to = self.config.get('reply_to', self.config['from'])
    if self.config['html']:
      body_html = '\n'.join(self.convert(reporters.HtmlReporter).submit())

      msg = mailer.msg_html(self.config['from'], self.config['to'], reply_to, subject, body_text, body_html)
    else:
      msg = mailer.msg_plain(self.config['from'], self.config['to'], reply_to, subject, body_text)

    mailer.send(msg)


class JiraReporter(reporters.ReporterBase):

  __kind__ = 'jira'

  # https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-bulk-post
  _MAX_BATCH_SIZE = 50

  _MAX_CONTENT_CHARS = 255
  # https://community.atlassian.com/t5/Jira-questions/Re-ADF-Content-Size-Limit-CONTENT-LIMIT-EXCEEDED-Error/qaq-p/1927334/comment-id/652431#M652431
  _MAX_MULTILINE_CONTENT_CHARS = 32767

  def submit(self):
    def _do_report(job_state):
      return (job_state.verb in ['error', 'changed'] and
        job_state.job.get_location() != 'date')

    issues = []
    changes = [j for j in
      self.report.get_filtered_job_states(self.job_states) if _do_report(j)]
    if not self.config['assignees']:
      logger.error('At least one assignee is required')
      return
    num_changed = len([c for c in changes if c.verb == 'changed'])
    num_errored = len([c for c in changes if c.verb == 'error'])
    job_pool_size = num_changed
    error_assignee = self.config.get('error_assignee', '')
    if not error_assignee:
      # If there is no error assignee, error jobs get auto-assigned like any
      # other job.
      job_pool_size += num_errored
    issues_per_assignee = job_pool_size / len(self.config['assignees'])
    job_pool_idx = 0
    for job_state in changes:
      issue_type_id = self.config['update_type']
      if job_state.verb == 'error':
        issue_type_id = self.config['error_type']
      issue = {
        'fields': {
          'project': {'id': self.config['project']},
          'issuetype': {'id': issue_type_id},
        },
      }
      pretty_name = job_state.job.pretty_name()
      loc = job_state.job.get_location()
      summary_parts = [f'{job_state.verb}:', pretty_name]
      if len(loc) <= self._MAX_CONTENT_CHARS:
        issue['fields'][self.config['url_field']] = loc
      if loc != pretty_name:
        summary_parts.append(f'({loc})')
      summary = ' '.join(summary_parts)
      if len(summary) > self._MAX_CONTENT_CHARS:
        ellipsis = '...'
        summary = summary[:self._MAX_CONTENT_CHARS - len(ellipsis)] + ellipsis
      issue['fields']['summary'] = summary
      details_url_args = {
        'datetime': self.report.start.strftime('%Y-%m-%d-%H%M%S'),
      }
      details_url = self.config['details_url'].format(**details_url_args)
      quoted_find_text = urllib.parse.quote(summary, safe='').replace('-', '%2D')
      details_anchor = f'#:~:text={quoted_find_text}'
      description = self._adf_doc()
      description['content'].extend(self._adf_header(''.join([details_url, details_anchor]), loc))
      if job_state.verb == 'error':
          description['content'].append(self._adf_text(job_state.traceback.strip()))
      elif job_state.verb == 'changed':
          description['content'].append(self._adf_diff(job_state.get_diff()))
      # Check that the description is within the character limit by experimentally
      # converting to a string.
      desc_str = json.dumps(description, separators=(',', ':'))
      if len(desc_str) > self._MAX_MULTILINE_CONTENT_CHARS:
        # Remove main content
        description['content'] = description['content'][:-1]
        # Add in a "this is too long" message
        description['content'].append(self._adf_text(
          'This change is too large to display.  Visit the full report above to view this change.'))
      issue['fields']['description'] = description
      issue['fields'][self.config['reported_field']] = datetime.date.today().strftime('%Y-%m-%d')
      if error_assignee and job_state.verb == 'error':
        assignee = error_assignee
        logger.debug('overriding normal assignee to be %s', assignee)
      else:
        assignee_idx = 0
        if issues_per_assignee > 0:
          assignee_idx = int(job_pool_idx / issues_per_assignee)
        assignee = self.config['assignees'][assignee_idx]
      issue['fields']['assignee'] = {'id': assignee}
      issue['fields']['duedate'] = (datetime.date.today() + datetime.timedelta(days=3)).strftime('%Y-%m-%d')
      filtered_reviewers = [r for r in self.config['reviewers'] if r != assignee]
      if (filtered_reviewers):
        issue['fields'][self.config['reviewer_field']] = [{'id': random.choice(filtered_reviewers)}]
      issues.append(issue)
      if not error_assignee:
        job_pool_idx += 1
      elif job_state.verb == 'changed':
        job_pool_idx += 1
    logger.debug('Generated %d issues for Jira', len(issues))
    # Reverse the order so that the default sorting order in Jira matches the
    # order in other reports.
    issues.reverse()
    self._create_issues(issues)


  def _create_issues(self, issues):
    # Make sure there's an entry in .netrc matching the host (or default).
    try:
      netrc_obj = netrc.netrc()
    except FileNotFoundError as e:
      logging.error(f'The {self.__kind__} reporter requires API '
        'credentials to be stored in a .netrc file, and that file does not '
        'seem to exist.')
      return
    netloc = urllib.parse.urlparse(self.config['site_url']).netloc
    if not netrc_obj.authenticators(netloc):
      logging.error(f'{netloc} was not found in your '
        '.netrc file and no default credentials exist in that file.\nAdd Jira '
        'API credentials to your .netrc file to use this reporter.')
      return
    for chunk in chunkify(issues, self._MAX_BATCH_SIZE):
      # Note auth is set by a local .netrc file with an entry for
      # the value of self.config['site_url']
      response = requests.post(
        urllib.parse.urljoin(self.config['site_url'], 'rest/api/3/issue/bulk'),
        headers={
          "Accept": "application/json",
          "Content-Type": "application/json"
         },
        json={'issueUpdates': chunk},
        params={'notifyUsers': 'false'},
      )
      try:
        resp_json = response.json()
        resp_text = json.dumps(resp_json, indent=2)
        num_uploaded = len(resp_json['issues'])
        issue_errors = resp_json['errors']
      except requests.exceptions.JSONDecodeError:
        resp_text = response.text
        num_uploaded = 'new'
        issue_errors = []
      if not response.ok:
        # No issues were uploaded
        logger.error(
          f'Error {response.status_code}: {resp_text}\nRequest body:\n{chunk}')
      else:
        # Some (or all) issues were uploaded
        logger.debug(f'Jira API response:\n{resp_text}')
        logger.debug(f'Uploaded {num_uploaded} issues to Jira')
        if issue_errors:
          logger.error(f'Not all issues were successfully uploaded to Jira. Errors: {issue_errors}')

  def _adf_doc(self):
    return {
      'type': 'doc',
      'version': 1,
      'content': []
    }

  def _adf_header(self, report_url, watched_url):
    return [
      {
        'type': 'paragraph',
        'content': [
          {
            'type': 'text',
            'text': 'See full change report here',
            'marks': [
              {
                'type': 'link',
                'attrs': {
                  'href': report_url
                }
              }
            ]
          },
        ]
      },
      {
        'type': 'paragraph',
        'content': [
          {
            'type': 'text',
            'text': 'Visit watched URL here',
            'marks': [
              {
                'type': 'link',
                'attrs': {
                  'href': watched_url
                }
              }
            ]
          },
        ]
      },
      {
       "type": "rule"
      },
    ]

  def _adf_diff(self, diff):
    adf = {
      'type': 'paragraph',
      'content': [
        {
          'text': '',
          'type': 'text',
        }
      ]
    }
    for line in diff.splitlines(keepends=True):
      if line.startswith('@@'):
        line = '\n< ... >\n\n'
      elif line.startswith('--- @'):
        line = line.replace('--- @', '- old:')
      elif line.startswith('+++ @'):
        line = line.replace('+++ @', '+ new:')

      if line.startswith('+'):
        adf['content'].append({
          'text': line,
          'type': 'text',
          'marks': [
            {'type': 'strong'},
            {'type': 'textColor', 'attrs': {'color': '#1f883d'}},
          ],
        })
      elif line.startswith('-'):
        adf['content'].append({
          'text': line,
          'type': 'text',
          'marks': [
            {'type': 'strong'},
            {'type': 'textColor', 'attrs': {'color': '#cf222e'}},
          ],
        })
      else:
        if 'marks' in adf['content'][-1]:
          # Last content node is a colored one.  Create a new one for the plain
          # text.
          adf['content'].append({
            'text': line,
            'type': 'text',
          })
        else:
          # Last content node is plain text.  Just append this line onto that
          # text node.
          adf['content'][-1]['text'] += line
    return adf

  def _adf_text(self, text):
    return {
      'type': 'paragraph',
      'content': [
        {
          'text': text,
          'type': 'text'
        }
      ]
    }
