import json  # TODO: remove
import logging
import netrc
import os
import pprint # TODO: remove
import re
import subprocess
import time
import urllib.parse

from bs4 import BeautifulSoup
import requests
from urlwatch import filters
from urlwatch import reporters
from urlwatch.mailer import SMTPMailer
from urlwatch.mailer import SendmailMailer

logger = logging.getLogger(__name__)


# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunkify(lst, n):
  """Yield n-sized chunks from the list 'lst'."""
  for i in range(0, len(lst), n):
      yield lst[i:i + n]


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


class RealPageBase(filters.FilterBase):
  def filter(self, data, subfilter):
    filtered = filters.FilterBase.process('jq', {'query': self.__query__}, self.state, data)
    filtered = filters.FilterBase.process('remove-duplicate-lines', {}, self.state, filtered)
    filtered = filters.FilterBase.process('sort', {}, self.state, filtered)
    filtered = filters.FilterBase.process('re.sub', {'pattern': '"'}, self.state, filtered)
    filtered = filters.FilterBase.process('re.sub', {'pattern': r'\\n', 'repl': r'\n'}, self.state, filtered)
    return filtered


class RealPageUnits(RealPageBase):
  """Filter for pretty-printing units JSON data from the realpage API."""

  __kind__ = 'realpage_units'
  __query__ = r'.response // . | .units[]? | "\(.numberOfBeds) BR\n---\n$\(.rent)/month\n\(.leaseStatus)\n\n"'


class RealPageFloorplans(RealPageBase):
  """Filter for pretty-printing floorplan JSON data from the realpage API."""

  __kind__ = 'realpage_floorplans'
  __query__ = r'.response // . | .floorplans[]? | "\(.name)\n---\n\(.bedRooms) BR\n\(.rentType)\n\(.rentRange)\n\n"'


class RegexSuperSub(filters.FilterBase):
  """Replace text with regex; can match within a line or substring."""

  __kind__ = 're.ssub'

  __supported_subfilters__ = {
    'substring': 'Regular expression for a substring to find "pattern" within',
    'pattern': 'Regular expression to search for (required)',
    'repl': 'Replacement string (default: empty string)',
  }

  __default_subfilter__ = 'pattern'

  def filter(self, data, subfilter):
    def replaceWithin(match):
      return re.sub(subfilter['pattern'], subfilter.get('repl', ''), match[0])
    if 'pattern' not in subfilter:
      raise ValueError('{} needs a pattern'.format(self.__kind__))
    # Default: Replace with empty string if no "repl" value is set
    if 'substring' in subfilter:
      return re.sub(subfilter['substring'], replaceWithin, data)
    else:
      return re.sub(subfilter['pattern'], subfilter.get('repl', ''), data)


class GcsFileReporter(reporters.HtmlReporter):
  """Custom reporter that writes an HTML file to Google Cloud Storage."""

  __kind__ = 'gcs'

  def submit(self):
    filename_args = {
      'datetime': self.report.start.strftime('%Y-%m-%d-%H%M%S'),
    }
    filename = self.config['filename'].format(**filename_args)
    local_path = os.path.join(os.path.expanduser(self.config['local_dir']), filename)
    # TODO: make necessary parent directories
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
    body_text = """
The following websites have changed.

For details, visit %s

%s
""" % (details_url, body_text)

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


class JiraReporter(reporters.HtmlReporter):

  __kind__ = 'jira'

  # https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-bulk-post
  _MAX_BATCH_SIZE = 50

  def submit(self):
    html_report = '\n'.join(super().submit())
    self._submit_from_html(html_report)

  def _create_issues(self, issues):
    # Make sure there's an entry in .netrc matching the host (or default).
    try:
      netrc_obj = netrc.netrc()
    except FileNotFoundError as e:
      logging.error(f'The {self.__kind__} reporter requires API '
        'credentials to be stored in a .netrc file, and that file does not '
        'seem to exist.')
      raise
    netloc = urllib.parse.urlparse(self.config['site_url']).netloc
    if not netrc_obj.authenticators(netloc):
      raise RuntimeError(f'{netloc} was not found in your '
        '.netrc file and no default credentials exist in that file.\nAdd Jira '
        'API credentials to your .netrc file to use this reporter.')
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
      )
      print(response.status_code)
      response.raise_for_status()

  def _submit_from_html(self, html):
    soup = BeautifulSoup(html, 'lxml')
    issues = []
    local_time = time.localtime()
    for heading in soup.find_all('h2'):
      verb = heading.find('span', class_='verb')
      if verb.string not in ['error:', 'changed:']:
        continue
      issue = {
        'fields': {
          'project': {'id': self.config['project']},
          'issuetype': {'id': self.config['issuetype']},
        },
      }
      title = verb.next_sibling.next_sibling
      url = title['href']
      summary_parts = [str(verb.string.capitalize()), str(title.string)]
      if url:
        issue['fields'][self.config['url_field']] = url
        if url != title.string:
          summary_parts.append(f'({url})')
      summary = ' '.join(summary_parts)
      issue['fields']['summary'] = summary
      content = heading.next_sibling.next_sibling
      if content.name == 'table':
        issue['fields']['description'] = self._format_table(content)
      else:
        issue['fields']['description'] = self._format_text(content)
      issue['fields'][self.config['reported_field']] = time.strftime(
        '%Y-%m-%d', local_time)
      issues.append(issue)
    # print(issues)
    self._create_issues(issues)

  def _format_table(self, tag):
    headers = tag.find_all('th', class_='diff_header')
    adf_headers = []
    for header in headers:
      adf_headers.extend([
        {
          'type': 'tableHeader',
          'attrs': {
            'colwidth': [48]
          },
          'content': [
            {
              'type': 'paragraph',
              'content': []
            }
          ]
        },
        {
          'type': 'tableHeader',
          'attrs': {
            'colwidth': [373]
          },
          'content': [
            {
              'type': 'paragraph',
              'content': [
                {
                  'type': 'text',
                  'text': '' if header.string is None else str(header.string),
                  'marks': [
                    {
                      'type': 'strong'
                    }
                  ]
                }
              ]
            }
          ]
        }
      ])
    rows = tag.find_all('tr')
    adf_rows = [
      {
        'type': 'tableRow',
        'content': adf_headers,
      },
    ]
    for row in rows:
      cells = row.find_all('td')
      adf_cells = []
      for cell in cells:
        if 'diff_next' in cell.get('class', []):
          continue
        adf_cells.append(
          {
            'type': 'tableCell',
            'content': [
              {
                'type': 'paragraph',
                'content': [
                  {
                    'type': 'text',
                    'text': '' if cell.string is None else str(cell.string),
                  }
                ]
              }
            ]
          }
        )
      if not adf_cells:
        continue
      adf_rows.append({
        'type': 'tableRow',
        'content': adf_cells,
      })

    ret = {
      'type': 'doc',
      'version': 1,
      'content': [
        {
          'type': 'paragraph',
          'content': [
            {
              'type': 'text',
              'text': 'Link to the original change report',
              'marks': [
                {
                  'type': 'link',
                  'attrs': {
                    'href': 'https://example.com'
                  }
                }
              ]
            }
          ]
        },
        {
          'type': 'table',
          'attrs': {
            'isNumberColumnEnabled': False,
            'layout': 'default',
          },
          'content': adf_rows,
        },
      ]
    }
    print(json.dumps(ret, indent=2))
    return ret

  def _format_text(self, tag):
    return {
      'type': 'doc',
      'version': 1,
      'content': [
        {
          'type': 'paragraph',
          'content': [
            {
              'text': '' if tag.string is None else str(tag.string),
              'type': 'text'
            }
          ]
        }
      ]
    }
