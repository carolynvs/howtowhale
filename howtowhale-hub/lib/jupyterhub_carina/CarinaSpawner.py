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
        'port_bindings': {8888: None}
    }

    @property
    def client(self):
        carina_dir = self.get_user_credentials_dir()
        tls_config = docker.tls.TLSConfig(
            client_cert=(os.path.join(carina_dir, 'cert.pem'),
                         os.path.join(carina_dir, 'key.pem')),
            ca_cert=os.path.join(carina_dir, 'ca.pem'),
            verify=os.path.join(carina_dir, 'ca.pem'),
            assert_hostname=False)
        with open(os.path.join(carina_dir, 'docker.env')) as f:
            env = f.read()
        docker_host = re.findall("DOCKER_HOST=tcp://(\d+\.\d+\.\d+\.\d+:\d+)", env)[0]
        docker_host = 'https://' + docker_host
        client = docker.Client(version='auto', tls=tls_config, base_url=docker_host, timeout=300)

        return client

    @gen.coroutine
    def get_container(self):
        if not self.container_id:
            return None

        self.log.debug("Getting container: %s", self.container_id)
        try:
            container = yield self.docker(
                'inspect_container', self.container_id
            )
            self.container_id = container['Id']
        except APIError as e:
            if e.response.status_code == 404:
                self.log.info("Container '%s' is gone", self.container_id)
                container = None
                # my container is gone, forget my id
                self.container_id = ''
            else:
                raise
        return container

    @gen.coroutine
    def start(self):
        try:
            self.log.info("Creating notebook infrastructure for {}...".format(self.user.name))

            yield self.create_cluster()
            yield self.download_cluster_credentials()
            yield self.pull_image()

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

            container = yield self.get_container()
            if container is not None:
                node_name = container['Node']['IP']
                self.user.server.ip = node_name
                self.log.info("{} was started on {} ({}:{})".format(
                    self.container_name, node_name, self.user.server.ip, self.user.server.port))

            self.log.debug('Startup for {} is complete!'.format(self.user.name))
        except Exception as e:
            self.log.error('Startup for {} failed!'.format(self.user.name))
            self.log.exception(e)
            raise

    @gen.coroutine
    def poll(self):
        """Check for my id in `docker ps`"""
        container = yield self.get_container()
        if not container:
            self.log.info("Notebook container for {} was not found".format(self.user.name))
            return ""

        container_state = container['State']
        self.log.debug(
            "Container %s status: %s",
            self.container_id[:7],
            pprint.pformat(container_state),
        )

        if container_state["Running"]:
            return None
        else:
            return (
                "ExitCode={ExitCode}, "
                "Error='{Error}', "
                "FinishedAt={FinishedAt}".format(**container_state)
            )

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
                 "Authorization": "Bearer {}".format(self.authenticator.oauth_token)}
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

        self.log.info("Downloading {} cluster credentials for {}...".format(self.cluster_name, self.user.name))

        http_client = AsyncHTTPClient()
        request = HTTPRequest(url=os.path.join(CARINA_CLUSTERS_URL, self.cluster_name),
                          method="GET",
                          headers={"Accept": "application/json",
                                   "User-Agent": "JupyterHub",
                                   "Authorization": "Bearer {}".format(self.authenticator.oauth_token)})

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
        docker_env_path = os.path.join(credentials_dir, "docker.env")
        if not os.path.exists(docker_env_path):
            raise RuntimeError("Unable to find docker.env")

        return credentials_dir

    @gen.coroutine
    def pull_image(self):
        self.log.debug("Starting to pull {} image to the {} cluster...".format(self.container_image, self.user.name))
        yield self.docker("pull", self.container_image)
        self.log.debug("Finished pulling {} image to the {} cluster...".format(self.container_image, self.user.name))
