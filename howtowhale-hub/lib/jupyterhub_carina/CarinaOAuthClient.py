import json
import logging
import os
from time import time
from tornado import gen
from tornado.httpclient import HTTPRequest, HTTPError, AsyncHTTPClient
import urllib

class CarinaOAuthCredentials:
    def __init__(self, access_token, refresh_token, expires_at):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at


class CarinaOAuthClient:
    CARINA_OAUTH_HOST = os.environ.get('CARINA_OAUTH_HOST') or 'oauth.getcarina.com'
    CARINA_AUTHORIZE_URL = "https://%s/oauth/authorize" % CARINA_OAUTH_HOST
    CARINA_TOKEN_URL = "https://%s/oauth/token" % CARINA_OAUTH_HOST
    CARINA_PROFILE_URL = "https://%s/me" % CARINA_OAUTH_HOST

    def __init__(self, client_id, client_secret, callback_url):
        self.log = logging.getLogger('jupyterhub_carina.CarinaOAuthClient')
        self.client_id = client_id
        self.client_secret = client_secret
        self.callback_url = callback_url

    @gen.coroutine
    def request_tokens(self, authorization_code):
        """
        Exchange an authorization code for an access token

        See: https://github.com/doorkeeper-gem/doorkeeper/wiki/API-endpoint-descriptions-and-examples#post---oauthtoken
        """
        http_client = AsyncHTTPClient()
        request = HTTPRequest(url=self.CARINA_TOKEN_URL,
                    method="POST",
                    body=urllib.parse.urlencode({
                        'code': authorization_code,
                        'redirect_uri': self.callback_url,
                        'grant_type': "authorization_code"
                    }),
                    headers={
                        'Accept': 'application/json',
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    auth_username=self.client_id,
                    auth_password=self.client_secret,
                    auth_mode='basic')

        request_timestamp = time()
        try:
            response = yield http_client.fetch(request)
        except HTTPError as e:
            self.log.exception('An error occurred while requesting an access token:\n(%s) %s', e.response.code, e.response.body)
            raise

        result = json.loads(response.body.decode('utf8', 'replace'))

        self.credentials = CarinaOAuthCredentials(
            access_token = result['access_token'],
            refresh_token = result['refresh_token'],
            expires_at = request_timestamp + int(result['expires_in']))

    @gen.coroutine
    def get_user_profile(self):
        # Determine who the logged in user is
        http_client = AsyncHTTPClient()
        request = HTTPRequest(
                    url=self.CARINA_PROFILE_URL,
                    method='GET',
                    headers={
                        'Accept': 'application/json',
                        'User-Agent': 'JupyterHub',
                        'Authorization': 'bearer {}'.format(self.credentials.access_token)
                    })
        try:
            response = yield http_client.fetch(request)
        except HTTPError as ex:
            self.log.exception('An error occurred while retrieving a user profile:\n(%s) %s', e.response.code, e.response.body)
            raise

        result = json.loads(response.body.decode('utf8', 'replace'))
        return result
