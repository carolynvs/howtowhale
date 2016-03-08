import json
from jupyterhub.auth import Authenticator
import os
import subprocess
import tempfile
from tornado.auth import OAuth2Mixin
from tornado import gen, web
from tornado.httpclient import HTTPRequest, HTTPError, AsyncHTTPClient
from traitlets import Unicode, Dict
from traitlets.config import LoggingConfigurable
import urllib
from .oauth2 import OAuthLoginHandler, OAuthenticator
from pprint import pformat


CARINA_OAUTH_HOST = os.environ.get('CARINA_OAUTH_HOST') or 'oauth.getcarina.com'
CARINA_OAUTH_ACCESS_TOKEN_URL = "https://%s/oauth/token" % CARINA_OAUTH_HOST
CARINA_OAUTH_IDENTITY_URL = "https://%s/me" % CARINA_OAUTH_HOST


class CarinaMixin(OAuth2Mixin):
    _OAUTH_AUTHORIZE_URL = "https://%s/oauth/authorize" % CARINA_OAUTH_HOST
    _OAUTH_ACCESS_TOKEN_URL = CARINA_OAUTH_ACCESS_TOKEN_URL

class CarinaLoginHandler(OAuthLoginHandler, CarinaMixin):
    scope = ['identity', 'cluster_credentials', 'create_cluster']

class CarinaAuthenticator(OAuthenticator, LoggingConfigurable):

    login_service = "Carina"
    client_id_env = 'CARINA_CLIENT_ID'
    client_secret_env = 'CARINA_CLIENT_SECRET'
    login_handler = CarinaLoginHandler

    username_map = Dict(config=True, default_value={},
                        help="""Optional dict to remap github usernames to nix usernames.

        User github usernames for keys and existing nix usernames as values.
        cf https://github.com/jupyter/oauthenticator/issues/28
        """)

    @gen.coroutine
    def authenticate(self, handler):
        code = handler.get_argument("code", False)
        if not code:
            raise web.HTTPError(400, "oauth callback made without a token")

        http_client = AsyncHTTPClient()

        # Exchange the OAuth code for a Carina Access Token
        #
        # See: https://github.com/doorkeeper-gem/doorkeeper/wiki/API-endpoint-descriptions-and-examples#post---oauthtoken
        post_data = {
            'code': code,
            'redirect_uri': self.oauth_callback_url,
            'grant_type': "authorization_code"
        }
        req = HTTPRequest(url=CARINA_OAUTH_ACCESS_TOKEN_URL,
                          method="POST",
                          body=urllib.parse.urlencode(post_data),
                          headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                          auth_username=self.client_id,
                          auth_password=self.client_secret,
                          auth_mode="basic"
                          )

        resp = None
        try:
            resp = yield http_client.fetch(req)
        except HTTPError as ex:
            self.log.error(ex.response.body)
            self.log.exception(ex)
            raise

        resp_json = json.loads(resp.body.decode('utf8', 'replace'))

        self.oauth_token = resp_json['access_token']

        # Determine who the logged in user is
        headers={"Accept": "application/json",
                 "User-Agent": "JupyterHub",
                 "Authorization": "Bearer {}".format(self.oauth_token)
        }
        req = HTTPRequest(url=CARINA_OAUTH_IDENTITY_URL,
                          method="GET",
                          headers=headers
                          )
        resp = yield http_client.fetch(req)
        resp_json = json.loads(resp.body.decode('utf8', 'replace'))

        carina_username = resp_json["username"]
        #remap gihub username to system username
        nix_username = self.username_map.get(carina_username, carina_username)

        #check system username against whitelist
        if self.whitelist and nix_username not in self.whitelist:
            nix_username = None
        return nix_username
