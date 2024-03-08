import logging
import os
import re
import subprocess

from urlwatch import filters
from urlwatch import reporters
from urlwatch.mailer import SMTPMailer
from urlwatch.mailer import SendmailMailer

logger = logging.getLogger(__name__)


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
