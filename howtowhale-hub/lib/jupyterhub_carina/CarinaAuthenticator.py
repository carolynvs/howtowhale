import zipfile
from io import BytesIO
from tempfile import mkdtemp
from os.path import join as pjoin
from os.path import split as psplit

from tornado import gen, web

from jupyterhub.auth import Authenticator


class CarinaAuthenticator(Authenticator):
    custom_html = """
    <form enctype="multipart/form-data" action="login" method="post">

    <p class="help-block">Sign in with your <a href="https://getcarina.com">Carina</a> account.</p>

    <label for="username_input">Carina User:</label>
    <input
      id="username_input"
      type="username"
      autocapitalize="off"
      autocorrect="off"
      class="form-control"
      name="username"
      tabindex="1"
      autofocus="autofocus"
    />
    <label for='password_input'>Carina API Key:</label>
    <input
      type="password"
      class="form-control"
      name="apikey"
      id="apikey_input"
      tabindex="2"
    />

    <input
      type="submit"
      id="login_submit"
      class='btn btn-jupyter'
      value='Sign In'
      tabindex="3"
    />
    </form>
    """

    @gen.coroutine
    def authenticate(self, handler, data):
        username = data['username']

        zf = zipfile.ZipFile(BytesIO(handler.request.files['zipfile'][0]['body']))

        cluster_name = psplit(zf.namelist()[0])[0]
        self.docker_env_dir = mkdtemp(suffix='-carinaauth')

        for name in ('docker.env', 'cert.pem', 'ca.pem', 'ca-key.pem', 'key.pem'):
            zf.extract(pjoin(cluster_name, name), path=self.docker_env_dir)

        self.docker_env_dir = pjoin(self.docker_env_dir, cluster_name)

        return username
