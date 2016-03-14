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

    cluster_name = "jupyterhub"
    volumes = { '/var/run/docker.sock': '/var/run/docker.sock' }

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
    def start(self, image=None):
        try:
            self.log.warn("starting notebook for {}...".format(self.user.name))

            yield self.create_cluster()
            yield self.download_cluster_credentials()

            self.log.warn("pulling image...")
            pull_kwargs = dict(repository="carolynvs/howtowhale-user")
            yield self.docker("pull", **pull_kwargs)
            self.log.warn("image pulled!")

            self.log.warn('starting user container...')
            yield super(CarinaSpawner, self).start(
                image=image,
                extra_host_config={'port_bindings': {8888: None}},
            )

            container = yield self.get_container()
            if container is not None:
                node_name = container['Node']['IP']
                self.user.server.ip = node_name
                self.log.info("{} was started on {} ({}:{})".format(
                    self.container_name, node_name, self.user.server.ip, self.user.server.port))

            self.log.warn('startup complete!')
        except Exception as e:
            self.log.error('startup failed')
            self.log.exception(e)
            raise

    @gen.coroutine
    def poll(self):
        self.log.warn('polling...')

        """Check for my id in `docker ps`"""
        container = yield self.get_container()
        if not container:
            self.log.warn("container not found")
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

        def handle_request(response):
            nonlocal done

            if not response.error:
                done = True
                self.log.debug("Credentials received")
                return response.body

            if response.error.code == 404 and "cluster is not yet active" in response.body:
                # don't worry keep trying!
                self.log.debug("The {}/{} cluster is not yet active, retrying...".format(self.user.name, self.cluster_name))
                yield gen.sleep(30)
                return None
            else:
                # abort, something bad happened!
                self.log.error(response.response.body)
                self.log.exception(response.error)
                response.rethrow

        http_client = AsyncHTTPClient()
        headers={"Accept": "application/json",
                 "User-Agent": "JupyterHub",
                 "Authorization": "Bearer {}".format(self.authenticator.oauth_token)}
        req = HTTPRequest(url=os.path.join(CARINA_CLUSTERS_URL, self.cluster_name),
                          method="GET",
                          headers=headers)

        done = False
        #while not done:
        resp = yield http_client.fetch(req, callback=handle_request, raise_error=False)

        credentials_zip = ZipFile(resp.buffer, "r")
        credentials_zip.extractall("/root/.carina/clusters/{}".format(self.user.name))
        self.log.info("Credentials downloaded to /root/.carina/clusters/{}/{}".format(self.user.name, self.cluster_name))

    def get_user_credentials_dir(self):
        credentials_dir = "/root/.carina/clusters/{}/{}".format(self.user.name, self.cluster_name)
        self.log.info("The credentials directory is: {}".format(credentials_dir))

        docker_env_path = os.path.join(credentials_dir, "docker.env")
        self.log.info("The docker env path is: {}".format(docker_env_path))
        if not os.path.exists(docker_env_path):
            raise RuntimeError("Unable to find docker.env")

        return credentials_dir

    @gen.coroutine
    def pull_image(self):
        self.log.warn("pulling image...")

        output = yield self.docker("pull", "carolynvs/howtowhale-user")
        for line in output:
            self.log.warn(json.dumps(json.loads(line), indent=4))

        self.log.warn("image pulled!")
