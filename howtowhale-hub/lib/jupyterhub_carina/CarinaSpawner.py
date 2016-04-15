import docker
from dockerspawner import DockerSpawner
import os.path
import re
import requests
from tornado import gen
from traitlets import Unicode, Integer
from .CarinaOAuthClient import CarinaOAuthClient


class CarinaSpawner(DockerSpawner):

    # Expose configuration
    oauth_callback_url = Unicode(
        os.getenv('OAUTH_CALLBACK_URL', ''),
        config=True,
        help="""Callback URL to use.
        Typically `https://{host}/hub/oauth_callback`"""
    )

    client_id_env = 'OAUTH_CLIENT_ID'
    client_id = Unicode(config=True)
    def _client_id_default(self):
        return os.getenv(self.client_id_env, '')

    client_secret_env = 'OAUTH_CLIENT_SECRET'
    client_secret = Unicode(config=True)
    def _client_secret_default(self):
        return os.getenv(self.client_secret_env, '')

    cluster_name = Unicode(config=True, default_value='jupyterhub')

    cluster_polling_interval = Integer(config=True, default_value=30)

    extra_host_config = {
        'volumes_from': ['swarm-data'],
        'port_bindings': {8888: None},
        'restart_policy': {
            'MaximumRetryCount': 0,
            'Name': 'always'
        }
    }

    def __init__(self, **kwargs):
        # Use a different docker client for each server
        self._client = None
        self._carina_client = None
        
        super().__init__(**kwargs)

    @property
    def client(self):
        """
        The Docker client used to connect to the user's Carina cluster
        """

        # TODO: Figure out how to configure this without overriding, or tweak a bit and call super
        if self._client is None:
            carina_dir = self.get_user_credentials_dir()
            docker_env = os.path.join(carina_dir, 'docker.env')
            if not os.path.exists(docker_env):
                raise RuntimeError("ERROR! The credentials for {}/{} could not be found in {}.".format(
                    self.user.name, self.cluster_name, carina_dir))

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

    @property
    def carina_client(self):
        if self._carina_client is None:
            # If we just authenticated, use the existing client which has the credentials loaded
            # Otherwise, make a new client and assume that load_state is about to be called next with the credentials
            if self.authenticator and self.authenticator.carina_client.credentials:
                self.log.debug("Using the Carina client for %s from the CarinaAuthenticator", self.user.name)
                self._carina_client = self.authenticator.carina_client
                self._carina_client.user = self.user.name
            else:
                self.log.debug("Initializing a carina client for %s", self.user.name)
                self._carina_client = CarinaOAuthClient(self.client_id, self.client_secret, self.oauth_callback_url, user=self.user.name)

        return self._carina_client

    def get_state(self):
        self.log.debug("Saving state for %s", self.user.name)
        state = super().get_state()
        if self.carina_client.credentials:
            state['access_token'] = self.carina_client.credentials.access_token
            state['refresh_token'] = self.carina_client.credentials.refresh_token
            state['expires_at'] = self.carina_client.credentials.expires_at

        return state

    def load_state(self, state):
        self.log.debug("Loading state for %s", self.user.name)
        super().load_state(state)

        access_token = state.get('access_token', None)
        refresh_token = state.get('refresh_token', None)
        expires_at = state.get('expires_at', None)
        if access_token:
            self.log.debug("Loading users's oauth credentials")
            self.carina_client.load_credentials(access_token, refresh_token, expires_at)

    def clear_state(self):
        self.log.debug("Clearing state")
        super().clear_state()

        # TODO: Move this to DockerSpawner
        self.container_id = ''

    @gen.coroutine
    def get_container(self):
        if not os.path.exists(self.get_user_credentials_dir()):
            return None

        if not self.cluster_exists():
            return None

        container = yield super().get_container()
        return container

    @gen.coroutine
    def start(self):
        try:
            self.log.info("Creating notebook infrastructure for {}...".format(self.user.name))

            yield self.create_cluster()
            yield self.download_cluster_credentials()
            yield self.pull_user_image()

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
            self.log.exception('Startup for {} failed!'.format(self.user.name))
            raise

    @gen.coroutine
    def create_cluster(self):
        """
        Create a Carina cluster.
        The API will return the cluster information if it already exists,
        so it's safe to call without checking if it exists first.
        """
        self.log.info("Creating cluster named: {} for {}".format(self.cluster_name, self.user.name))
        yield self.carina_client.create_cluster(self.cluster_name)

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

        self.log.info("Downloading cluster credentials for {}/{}...".format(self.user.name, self.cluster_name))
        user_dir = "/root/.carina/clusters/{}".format(self.user.name)
        yield self.carina_client.download_cluster_credentials(self.cluster_name, user_dir, self.cluster_polling_interval)

    @gen.coroutine
    def cluster_exists(self):
        try:
            yield self.docker('info')
            return True
        except requests.exceptions.RequestException:
            return False

    @gen.coroutine
    def pull_user_image(self):
        """
        Pull the user image to the cluster, so that it is ready to start instantly
        """
        self.log.debug("Starting to pull {} to the {}/{} cluster..."
                       .format(self.container_image, self.user.name, self.cluster_name))
        yield self.docker("pull", self.container_image)
        self.log.debug("Finished pulling {} to the {}/{} cluster..."
                       .format(self.container_image, self.user.name, self.cluster_name))

    def get_user_credentials_dir(self):
        credentials_dir = "/root/.carina/clusters/{}/{}".format(self.user.name, self.cluster_name)
        return credentials_dir
