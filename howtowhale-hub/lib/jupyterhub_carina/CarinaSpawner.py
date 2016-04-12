import docker
from docker.errors import APIError
from dockerspawner import DockerSpawner
import json
import os.path
import pprint
import re
from io import StringIO
from tornado import gen
from tornado.httpclient import HTTPRequest, HTTPError, AsyncHTTPClient
from zipfile import ZipFile


CARINA_OAUTH_HOST = os.environ.get('CARINA_OAUTH_HOST') or 'oauth.getcarina.com'
CARINA_CLUSTERS_URL = "https://%s/clusters" % CARINA_OAUTH_HOST


class CarinaSpawner(DockerSpawner):

    cluster_name = "howtowhale"
    cluster_polling_interval = 30
    extra_host_config = {
        'volumes_from': ['swarm-data'],
        'port_bindings': {8888: None},
        'restart_policy': {
            'MaximumRetryCount': 0,
            'Name': 'always'
        }
    }

    _client = None
    @property
    def client(self):
        """
        The Docker client used to connect to the user's Carina cluster
        """

        # Use the same client for each Spawner instance
        if self._client is None:
            carina_dir = self.get_user_credentials_dir()
            docker_env = os.path.join(carina_dir, 'docker.env')
            if not os.path.exists(docker_env):
                raise RuntimeError("ERROR! The credentials for {}/{} could not be found in {}.".format(self.user.name, self.cluster_name, carina_dir))

            tls_config = docker.tls.TLSConfig(
                client_cert=(os.path.join(carina_dir, 'cert.pem'),
                             os.path.join(carina_dir, 'key.pem')),
                ca_cert=os.path.join(carina_dir, 'ca.pem'),
                verify=os.path.join(carina_dir, 'ca.pem'),
                assert_hostname=False)
            with open(docker_env) as f:
                env = f.read()
            docker_host = re.findall("DOCKER_HOST=tcp://(\d+\.\d+\.\d+\.\d+:\d+)", env)[0]
            docker_host = 'https://' + docker_host
            self._client = docker.Client(version='auto', tls=tls_config, base_url=docker_host)

        return self._client

    _oauth_token = None
    @property
    def oauth_token(self):
        if self._oauth_token is None:
            self._oauth_token = self.retrieve_oauth_token()

        return self._oauth_token

    def get_state(self):
        state = super().get_state()
        if self.oauth_token:
            state["oauth_token"] = self.oauth_token

        return state

    def load_state(self, state):
        super().load_state(state)
        self._oauth_token = state.get("oauth_token", None)

    def clear_state(self):
        super().clear_state()
        # TODO: Move this to DockerSpawner
        self.container_id = ''

    @gen.coroutine
    def get_container(self):
        if not os.path.exists(self.get_user_credentials_dir()):
            return None

        container = yield super().get_container()
        return container

    @gen.coroutine
    def start(self):
        try:
            self.log.info("Creating notebook infrastructure for {}...".format(self.user.name))

            yield self.create_cluster()
            yield self.download_cluster_credentials()

            self.log.info("Starting notebook container for {}...".format(self.user.name))
            extra_env = {
                'DOCKER_HOST': self.client.base_url.replace("https://", "tcp://"),
                'DOCKER_TLS_VERIFY': 1,
                'DOCKER_CERT_PATH': '/var/run/docker/'
            }
            extra_env.update(self.get_env())
            extra_create_kwargs = {
                'environment': extra_env
            }

            yield super().start(extra_create_kwargs=extra_create_kwargs)

            self.log.debug('Startup for {} is complete!'.format(self.user.name))
        except Exception as e:
            self.log.error('Startup for {} failed!'.format(self.user.name))
            self.log.exception(e)
            raise

    @gen.coroutine
    def create_cluster(self):
        """
        Create a Carina cluster.
        The API will return the cluster information if it already exists,
        so it's safe to call without checking if it exists first.
        """
        self.log.info("Creating cluster named: {} for {}".format(self.cluster_name, self.user.name))

        http_client = AsyncHTTPClient()
        headers={"Accept": "application/json",
                 "User-Agent": "JupyterHub",
                 "Authorization": "Bearer {}".format(self.oauth_token)}
        req = HTTPRequest(url=os.path.join(CARINA_CLUSTERS_URL, self.cluster_name),
                          method="PUT",
                          body="{}",
                          headers=headers)


        try:
            yield http_client.fetch(req)
        except HTTPError as ex:
            self.log.error(ex.response.body)
            self.log.exception(ex)
            raise

    @gen.coroutine
    def download_cluster_credentials(self):
        """
        Download the cluster credentials
        The API will return 404 if the cluster isn't available yet,
        in which case the reqeust should be retried
        """
        credentials_dir = self.get_user_credentials_dir()
        if os.path.exists(credentials_dir):
            return

        self.log.info("Downloading {} cluster credentials for {}...".format(self.cluster_name, self.user.name))

        http_client = AsyncHTTPClient()
        request = HTTPRequest(url=os.path.join(CARINA_CLUSTERS_URL, self.cluster_name),
                          method="GET",
                          headers={"Accept": "application/json",
                                   "User-Agent": "JupyterHub",
                                   "Authorization": "Bearer {}".format(self.oauth_token)})

        while True:
            # TODO: Abort after some set timeout, does jupyterhub handle that for us?
            response = yield http_client.fetch(request, raise_error=False)

            if response.error is None:
                self.log.debug("Credentials for {}/{} received.".format(self.user.name, self.cluster_name))
                break

            if response.code == 404 and "cluster is not yet active" in response.body.decode(encoding='UTF-8'):
                self.log.info("The {}/{} cluster is not yet active, retrying in {}s...".format(self.user.name, self.cluster_name, self.cluster_polling_interval))
                yield gen.sleep(self.cluster_polling_interval)
                continue

            # abort, something bad happened!
            self.log.error(response.response.body)
            self.log.exception(response.error)
            response.rethrow

        credentials_zip = ZipFile(response.buffer, "r")
        credentials_zip.extractall("/root/.carina/clusters/{}".format(self.user.name))
        self.log.info("Credentials downloaded to /root/.carina/clusters/{}/{}".format(self.user.name, self.cluster_name))

    def get_user_credentials_dir(self):
        credentials_dir = "/root/.carina/clusters/{}/{}".format(self.user.name, self.cluster_name)
        return credentials_dir

    def retrieve_oauth_token(self):
        self.log.info("===retrieve oauth token===")
        if self.authenticator is None or not self.authenticator.oauth_token:
            raise RuntimeError("Could not find the oauth token for {}".format(self.user.name))

        return self.authenticator.oauth_token
