#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import httplib2
import logging
import os
import pickle

import cloudstorage as gcs

from googleapiclient import discovery
from oauth2client import client
from oauth2client.contrib import appengine
from google.appengine.api import memcache

from google.appengine.api import app_identity

import webapp2
import jinja2


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    autoescape=True,
    extensions=['jinja2.ext.autoescape'])

CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'client_secrets.json')

MISSING_CLIENT_SECRETS_MESSAGE = """
<h1>Warning: Please configure OAuth 2.0</h1>
<p>
To make this sample run you will need to populate the client_secrets.json file
found at:
</p>
<p>
<code>%s</code>.
</p>
<p>with information found on the <a
href="https://code.google.com/apis/console">APIs Console</a>.
</p>
""" % CLIENT_SECRETS

http = httplib2.Http(memcache)
service = discovery.build("plus", "v1", http=http)
decorator = appengine.oauth2decorator_from_clientsecrets(
    CLIENT_SECRETS,
    scope='https://www.googleapis.com/auth/plus.me',
    message=MISSING_CLIENT_SECRETS_MESSAGE)


class MainHandler(webapp2.RequestHandler):

    @decorator.oauth_aware
    def get(self):
        variables = {
            'url': decorator.authorize_url(),
            'has_credentials': decorator.has_credentials()
        }
        template = JINJA_ENVIRONMENT.get_template('grant.html')
        self.response.write(template.render(variables))


class AboutHandler(webapp2.RequestHandler):

    @decorator.oauth_required
    def get(self):
        try:
            http = decorator.http()
            user = service.people().get(userId='me').execute(http=http)
            text = 'Hello, %s!' % user['displayName']

            template = JINJA_ENVIRONMENT.get_template('welcome.html')
            self.response.write(template.render({'text': text }))
        except client.AccessTokenRefreshError:
            self.redirect('/')


class HelloHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('Hello world!')

class DataHandler(webapp2.RequestHandler):
    @decorator.oauth_required
    def get(self):
        bucket_name = os.environ.get('BUCKET_NAME',
                                     app_identity.get_default_gcs_bucket_name())

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write('Demo GCS Application running from Version: '
                            + os.environ['CURRENT_VERSION_ID'] + '\n')
        self.response.write('Using bucket name: ' + bucket_name + '\n\n')

    @decorator.oauth_required
    def create_file(self, filename):
        """Create a file.

        The retry_params specified in the open call will override the default
        retry params for this particular file handle.

        Args:
          filename: filename.
        """
        self.response.write('Creating file %s\n' % filename)

        write_retry_params = gcs.RetryParams(backoff_factor=1.1)
        gcs_file = gcs.open(filename,
                            'w',
                            content_type='text/plain',
                            options={'x-goog-meta-foo': 'foo',
                                     'x-goog-meta-bar': 'bar'},
                            retry_params=write_retry_params)
        gcs_file.write('abcde\n')
        gcs_file.write('f' * 1024 * 4 + '\n')
        gcs_file.close()
        self.tmp_filenames_to_clean_up.append(filename)

    @decorator.oauth_required
    def read_file(self, filename):
        self.response.write('Abbreviated file content (first line and last 1K):\n')

        gcs_file = gcs.open(filename)
        self.response.write(gcs_file.readline())
        gcs_file.seek(-1024, os.SEEK_END)
        self.response.write(gcs_file.read())
        gcs_file.close()

    @decorator.oauth_required
    def list_bucket(self, bucket):
        self.response.write('Listbucket result:\n')

        page_size = 1
        stats = gcs.listbucket(bucket + '/foo', max_keys=page_size)
        while True:
            count = 0
            for stat in stats:
                count += 1
                self.response.write(repr(stat))
                self.response.write('\n')

            if count != page_size or count == 0:
                break
            stats = gcs.listbucket(bucket + '/foo', max_keys=page_size,
                                   marker=stat.filename)

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/about', AboutHandler),
    ('/hello', HelloHandler),
    ('/data', DataHandler),
    (decorator.callback_path, decorator.callback_handler()),
], debug=True)



# class MainPage(webapp2.RequestHandler):
#     def get(self):
#         user = users.get_current_user()
#         if user:
#             nickname = user.nickname()
#             logout_url = users.create_logout_url('/')
#             greeting = 'Welcome, {}! (<a href="{}">sign out</a>)'.format(
#                 nickname, logout_url)
#         else:
#             login_url = users.create_login_url('/')
#             greeting = '<a href="{}">Sign in</a>'.format(login_url)
#
#         self.response.write(
#             '<html><body>{}</body></html>'.format(greeting))
