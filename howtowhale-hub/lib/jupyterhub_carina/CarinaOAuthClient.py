import json
import os
from time import time, ctime
from tornado import gen
from tornado.httpclient import HTTPRequest, HTTPError, AsyncHTTPClient
from traitlets.config import LoggingConfigurable
import urllib
from zipfile import ZipFile


class CarinaOAuthCredentials:
    def __init__(self, access_token, refresh_token, expires_at):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at

    def is_expired(self):
        return time() >= (self.expires_at + 60)


class CarinaOAuthClient(LoggingConfigurable):
    CARINA_OAUTH_HOST = os.environ.get('CARINA_OAUTH_HOST') or 'oauth.getcarina.com'
    CARINA_AUTHORIZE_URL = "https://%s/oauth/authorize" % CARINA_OAUTH_HOST
    CARINA_TOKEN_URL = "https://%s/oauth/token" % CARINA_OAUTH_HOST
    CARINA_PROFILE_URL = "https://%s/me" % CARINA_OAUTH_HOST
    CARINA_CLUSTERS_URL = "https://%s/clusters" % CARINA_OAUTH_HOST

    def __init__(self, client_id, client_secret, callback_url, user='UNKNOWN'):
        super().__init__()
        self.client_id = client_id
        self.client_secret = client_secret
        self.callback_url = callback_url
        self.credentials = None
        self.user = user

    def load_credentials(self, access_token, refresh_token, expires_at):
        self.credentials = CarinaOAuthCredentials(access_token, refresh_token, expires_at)

    @gen.coroutine
    def request_tokens(self, authorization_code):
        """
        Exchange an authorization code for access and refresh tokens

        See: https://github.com/doorkeeper-gem/doorkeeper/wiki/API-endpoint-descriptions-and-examples#post---oauthtoken
        """

        self.log.debug("Requesting oauth tokens")
        body = {
            'code': authorization_code,
            'grant_type': 'authorization_code'
        }

        yield self.execute_token_request(body)

    @gen.coroutine
    def refresh_tokens(self):
        """
        Exchange a refresh token for a new set of tokens

        See: https://github.com/doorkeeper-gem/doorkeeper/wiki/API-endpoint-descriptions-and-examples#curl-command-refresh-token-grant
        """

        self.log.info("Refreshing oauth tokens for %s", self.user)
        body = {
            'refresh_token': self.credentials.refresh_token,
            'grant_type': 'refresh_token'
        }

        yield self.execute_token_request(body)

    @gen.coroutine
    def get_user_profile(self):
        """
        Determine who the logged in user is
        """

        self.log.debug("Retrieving the user profile")
        request = HTTPRequest(
            url=self.CARINA_PROFILE_URL,
            method='GET',
            headers={
                'Accept': 'application/json',
            })
        response = yield self.execute_oauth_request(request)
        result = json.loads(response.body.decode('utf8', 'replace'))
        return result

    @gen.coroutine
    def create_cluster(self, cluster_name):
        """
        Create a Carina cluster
        """

        self.log.info("Creating cluster %s/%s", self.user, cluster_name)
        request = HTTPRequest(
            url=os.path.join(self.CARINA_CLUSTERS_URL, cluster_name),
            method='PUT',
            body='{}',
            headers={
                'Accept': 'application/json'
            })

        response = yield self.execute_oauth_request(request)
        result = json.loads(response.body.decode('utf8', 'replace'))
        return result

    @gen.coroutine
    def download_cluster_credentials(self, cluster_name, destination, polling_interval=30):
        """
        Download a cluster's credentials to the specified location.
        """

        self.log.info("Downloading cluster credentials for %s/%s", self.user, cluster_name)
        request = HTTPRequest(
            url=os.path.join(self.CARINA_CLUSTERS_URL, cluster_name),
            method='GET',
            headers={
                'Accept': 'application/zip'
            })

        # Poll for the cluster credentials until the cluster is active
        while True:
            response = yield self.execute_oauth_request(request, raise_error=False)

            if response.error is None:
                self.log.debug("Credentials for %s/%s received.", self.user, cluster_name)
                break

            if response.code == 404 and "cluster is not yet active" in response.body.decode(encoding='UTF-8'):
                self.log.debug("The %s/%s cluster is not yet active, retrying in %s seconds...",
                               self.user, cluster_name, polling_interval)
                yield gen.sleep(polling_interval)
                continue

            # abort, something bad happened!
            self.log.error('An error occurred while downloading cluster credentials for %s/%s:\n(%s) %s\n%s',
                           self.user, cluster_name, response.response.code, response.response.body, response.error)
            response.rethrow

        credentials_zip = ZipFile(response.buffer, "r")
        credentials_zip.extractall(destination)
        self.log.info("Credentials downloaded to %s", destination)

    @gen.coroutine
    def execute_token_request(self, body):
        """
        Requests a new set of OAuth tokens
        """

        body.update({
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.callback_url
        })

        request = HTTPRequest(
            url=self.CARINA_TOKEN_URL,
            method='POST',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body=urllib.parse.urlencode(body)
        )

        request_timestamp = time()
        response = yield self.execute_request(request)

        result = json.loads(response.body.decode('utf8', 'replace'))
        self.credentials = CarinaOAuthCredentials(
            access_token=result['access_token'],
            refresh_token=result['refresh_token'],
            expires_at=request_timestamp + int(result['expires_in']))

    @gen.coroutine
    def execute_oauth_request(self, request, raise_error=True):
        """
        Execute an OAuth request, retrying with a new set of tokens if the OAuth access token is expired or rejected
        """

        if self.credentials.is_expired():
            self.log.info("The OAuth token for %s expired at %s", self.user, ctime(self.credentials.expires_at))
            yield self.refresh_tokens()

        self.authorize_request(request)

        try:
            return (yield self.execute_request(request, raise_error))
        except HTTPError as e:
            if e.response.code != 401:
                raise

            # Try once more with a new set of tokens
            self.log.info("The OAuth token for %s were rejected", self.user)
            yield self.refresh_tokens()
            self.authorize_request(request)
            return (yield self.execute_request(request, raise_error))

    def authorize_request(self, request):
        """
        Add the Authorization header with the user's OAuth access token to a request
        """

        request.headers.update({
                'Authorization': 'bearer {}'.format(self.credentials.access_token)
            })

    @gen.coroutine
    def execute_request(self, request, raise_error=True):
        """
        Execute a HTTP request and log the error, if any
        """

        self.log.debug("%s %s", request.method, request.url)
        http_client = AsyncHTTPClient()
        request.headers.update({
                'User-Agent': 'jupyterhub'
            })
        try:
            return (yield http_client.fetch(request, raise_error=raise_error))
        except HTTPError as e:
            self.log.exception('An error occurred executing %s %s:\n(%s) %s',
                               request.method, request.url, e.response.code, e.response.body)
            raise
