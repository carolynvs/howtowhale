import re
from os.path import join as pjoin
import pdb
import subprocess
from tornado import gen
import os.path
import docker
from docker.errors import APIError
import pprint
from dockerspawner import DockerSpawner
from io import BytesIO
import tarfile

class CarinaSpawner(DockerSpawner):

    def __init__(self, **kwargs):
        super(CarinaSpawner, self).__init__(**kwargs)

        self.starting = False
        self.started = False

    @property
    def client(self):
        carina_dir = self.get_user_credentials_dir()
        tls_config = docker.tls.TLSConfig(
            client_cert=(pjoin(carina_dir, 'cert.pem'),
                         pjoin(carina_dir, 'key.pem')),
            ca_cert=pjoin(carina_dir, 'ca.pem'),
            verify=pjoin(carina_dir, 'ca.pem'),
            assert_hostname=False)
        with open(pjoin(carina_dir, 'docker.env')) as f:
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
            self.starting = True
            self.log.warn("starting notebook for {}...".format(self.user.name))

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

            yield self.move_user_credentials()

            self.started = True
            self.starting = False
            self.log.warn('startup complete!')
        except Exception as e:
            self.log.error('startup failed')
            self.log.exception(e)

    @gen.coroutine
    def poll(self):
        self.log.warn('polling...')
        if self.starting and not self.started:
            self.log.warn("startup is still in-progress!")
            return None

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

    def get_user_credentials_dir(self):
        credentials_dir = "/root/.carina/clusters/{}/howtowhale".format(self.user.name)
        self.log.info("The credentials directory is: {}".format(credentials_dir))

        docker_env_path = os.path.join(credentials_dir, "docker.env")
        self.log.info("The docker env path is: {}".format(docker_env_path))
        if(not os.path.exists(docker_env_path)):
            raise RuntimeError("Unable to find docker.env")

        return credentials_dir

    def pull_image(self):
        self.log.warn("pulling image...")

        output = yield self.docker("pull", "carolynvs/howtowhale-user")
        for line in output:
            self.log.warn(json.dumps(json.loads(line), indent=4))

        self.log.warn("image pulled!")

    def is_image_pulled(self):
        self.log.warn("Checking if the image has been pulled...")

        images_kwargs = dict(name="carolynvs/howtowhale-user", quiet=True)
        images = yield self.docker('images', **images_kwargs)
        self.log.warn("got images")
        self.log.warn(images)
        if len(images) == 0:
            self.log.warn("image is not yet pulled")
            return False

        return True
        self.log.warn("found image!")

    @gen.coroutine
    def move_user_credentials(self):
        self.log.warn("Moving user credentials from the hub to the user's notebook container...")

        credentials_src = "/root/.carina/clusters/{}".format(self.user.name)
        credentials_archive = BytesIO()
        tar = tarfile.open(mode = "w", fileobj = credentials_archive)
        #tar = tarfile.open(credentials_src + "/creds.tar", mode='w')
        tar.add(credentials_src, arcname=".carina/clusters/{}".format(self.user.name))
        tar.close()
        credentials_archive.seek(0)

        credentials_dest = "/home/jovyan"
        success = yield self.docker("put_archive", self.container_id, credentials_dest, credentials_archive)
        if not success:
            raise RuntimeError("Unable to move Carina credentials from the hub to the user container!")

        self.log.warn("Fixing the user/owner of the credentials")
        result = yield self.docker("exec_create", self.container_id, "chown -R jovyan.users /home/jovyan/.carina")
        self.log.warn(result)
        result = yield self.docker("exec_start", result["Id"])
        self.log.warn(result)
