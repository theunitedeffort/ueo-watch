import difflib
import logging
import os
import re
import subprocess
import yaml

from urlwatch import filters
from urlwatch import reporters
from urlwatch.mailer import SMTPMailer
from urlwatch.mailer import SendmailMailer

logger = logging.getLogger(__name__)

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


class UpdateUrlsReporter(reporters.ReporterBase):
    """Uses job diffs to update a URLs YAML file for a later urlwatch run."""

    __kind__ = 'update_urls'

    @staticmethod
    def unmarkup(line):
        for mark in ['\0+', '\0-', '\0^', '\1']:
            line = line.replace(mark, '')
        return line.strip()

    def _change(self, old_loc, new_loc):
        subprocess.run([
            'urlwatch',
            '--urls',
            os.path.expanduser('~/projects/ueo-watch/housing_links/stage2/urls.yaml'),
            '--change-location',
            old_loc,
            new_loc 
        ])

    def _remove(self, loc):
        subprocess.run([
            'urlwatch',
            '--urls',
            os.path.expanduser('~/projects/ueo-watch/housing_links/stage2/urls.yaml'),
            '--delete',
            loc 
        ])

    def _add(self, loc):
        subprocess.run([
            'urlwatch',
            '--urls',
            os.path.expanduser('~/projects/ueo-watch/housing_links/stage2/urls.yaml'),
            '--add',
            'url=%s' % loc 
        ])

    def submit(self):
        href_regex = 'href="(.*?)"'
        for job_state in self.report.get_filtered_job_states(self.job_states):
            if job_state.verb == 'new':
                for line in job_state.new_data.splitlines():
                    match = re.search(href_regex, line)
                    if match:
                        print('NEW ADD %s' % match[1])
                        self._add(match[1])
            if not job_state.old_data:
                continue
            diffs = difflib._mdiff(job_state.old_data.splitlines(),
                job_state.new_data.splitlines())
            for from_data, to_data, changed in diffs:
                if not changed:
                    continue
                from_match = re.search(href_regex, unmarkup(from_data[1]))
                to_match = re.search(href_regex, unmarkup(to_data[1]))
                if from_match and to_match:
                    print('CHANGED %s --> %s' % (from_match[1], to_match[1]))
                    self._change(from_match[1], to_match[1])
                elif not from_match and to_match:
                    print('ADDED   %s' % to_match[1])
                    self._add(to_match[1])
                elif from_match and not to_match:
                    print('REMOVED %s' % from_match[1])
                    self._remove(from_match[1])
        

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

        if self.config['html']:
            body_html = '\n'.join(self.convert(reporters.HtmlReporter).submit())

            msg = mailer.msg_html(self.config['from'], self.config['to'], subject, body_text, body_html)
        else:
            msg = mailer.msg_plain(self.config['from'], self.config['to'], subject, body_text)

        mailer.send(msg)
