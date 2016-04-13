import json
import logging
import os
from time import time
from tornado import gen
from tornado.httpclient import HTTPRequest, HTTPError, AsyncHTTPClient
import urllib
from zipfile import ZipFile

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
    CARINA_CLUSTERS_URL = "https://%s/clusters" % CARINA_OAUTH_HOST

    def __init__(self, client_id, client_secret, callback_url):
        self.log = logging.getLogger('jupyterhub_carina.CarinaOAuthClient')
        self.client_id = client_id
        self.client_secret = client_secret
        self.callback_url = callback_url
        self.credentials = None

    def load_credentials(self, access_token, refresh_token, expires_at):
        self.credentials = CarinaOAuthCredentials(access_token, refresh_token, expires_at)

    @gen.coroutine
    def request_tokens(self, authorization_code):
        """
        Exchange an authorization code for an access token

        See: https://github.com/doorkeeper-gem/doorkeeper/wiki/API-endpoint-descriptions-and-examples#post---oauthtoken
        """
        http_client = AsyncHTTPClient()
        request = HTTPRequest(
            url=self.CARINA_TOKEN_URL,
            method='POST',
            body=urllib.parse.urlencode({
                'code': authorization_code,
                'redirect_uri': self.callback_url,
                'grant_type': 'authorization_code'
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
            self.log.exception('An error occurred while requesting an access token:\n(%s) %s',
                               e.response.code, e.response.body)
            raise

        result = json.loads(response.body.decode('utf8', 'replace'))

        self.credentials = CarinaOAuthCredentials(
            access_token=result['access_token'],
            refresh_token=result['refresh_token'],
            expires_at=request_timestamp + int(result['expires_in']))

    @gen.coroutine
    def get_user_profile(self):
        """
        Determine who the logged in user is
        """

        http_client = AsyncHTTPClient()
        request = HTTPRequest(
            url=self.CARINA_PROFILE_URL,
            method='GET',
            headers={
                'Accept': 'application/json',
                'User-Agent': 'jupyterhub',
                'Authorization': 'bearer {}'.format(self.credentials.access_token)
            })
        try:
            response = yield http_client.fetch(request)
        except HTTPError as e:
            self.log.exception('An error occurred while retrieving a user profile:\n(%s) %s',
                               e.response.code, e.response.body)
            raise

        result = json.loads(response.body.decode('utf8', 'replace'))
        return result

    @gen.coroutine
    def create_cluster(self, cluster_name):
        """
        Create a Carina cluster
        """

        http_client = AsyncHTTPClient()
        request = HTTPRequest(
            url=os.path.join(self.CARINA_CLUSTERS_URL, cluster_name),
            method='PUT',
            body='{}',
            headers={
                'Accept': 'application/json',
                'User-Agent': 'jupyterhub',
                'Authorization': 'bearer {}'.format(self.credentials.access_token)
            })

        try:
            response = yield http_client.fetch(request)
        except HTTPError as e:
            self.log.exception('An error occurred while creating a cluster:\n(%s) %s', e.response.code, e.response.body)
            raise

        result = json.loads(response.body.decode('utf8', 'replace'))
        return result

    @gen.coroutine
    def download_cluster_credentials(self, cluster_name, destination, polling_interval=30):
        """
        Download a cluster's credentials to the specified location.
        """
        http_client = AsyncHTTPClient()
        request = HTTPRequest(
            url=os.path.join(self.CARINA_CLUSTERS_URL, cluster_name),
            method='GET',
            headers={
                'Accept': 'application/zip',
                'User-Agent': 'jupyterhub',
                'Authorization': 'bearer {}'.format(self.credentials.access_token)
            })

        while True:
            response = yield http_client.fetch(request, raise_error=False)

            if response.error is None:
                self.log.debug("Credentials for {} received.".format(cluster_name))
                break

            if response.code == 404 and "cluster is not yet active" in response.body.decode(encoding='UTF-8'):
                self.log.debug("The {} cluster is not yet active, retrying in {}s..."
                               .format(cluster_name, polling_interval))
                yield gen.sleep(polling_interval)
                continue

            # abort, something bad happened!
            self.log.error('An error occurred while downloading cluster credentials:\n(%s) %s\n%s',
                           response.response.code, response.response.body, response.error)
            response.rethrow

        credentials_zip = ZipFile(response.buffer, "r")
        credentials_zip.extractall(destination)
        self.log.info("Credentials downloaded to {}".format(destination))
