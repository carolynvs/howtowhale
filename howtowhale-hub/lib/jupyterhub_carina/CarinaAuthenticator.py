import os
import subprocess
import tempfile
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
        apikey = data['apikey']

        if not self.check_whitelist(username):
            self.log.warning("User %r not in whitelist.", username)
            return None

        if(not self.authenticate_to_carina(username, apikey)):
            return None

        if(not self.user_cluster_exists(username, apikey)):
            self.create_user_cluster(username, apikey)

        self.download_user_cluster_credentials(username, apikey)

        return username

    def authenticate_to_carina(self, username, apikey):
        return self.list_clusters(username, apikey) == 0

    def list_clusters(self, username, apikey):
        from subprocess import call

        userenv = os.environ.copy()
        userenv["CARINA_USERNAME"]=username
        userenv["CARINA_APIKEY"]=apikey

        return subprocess.call(["carina", "ls", "--no-cache"], env=userenv)

    def user_cluster_exists(self, username, apikey):
        from subprocess import call

        userenv = os.environ.copy()
        userenv["CARINA_USERNAME"]=username
        userenv["CARINA_APIKEY"]=apikey

        return subprocess.call(["carina", "get", "--no-cache", "howtowhale"], env=userenv) == 0

    def create_user_cluster(self, username, apikey):
        from subprocess import call

        userenv = os.environ.copy()
        userenv["CARINA_USERNAME"]=username
        userenv["CARINA_APIKEY"]=apikey

        result = subprocess.call(["carina", "create", "--no-cache", "--wait", "howtowhale"], env=userenv)
        if(result != 0):
            raise RuntimeError("Unable to create a cluster for the user: {}".format(username))

    def download_user_cluster_credentials(self, username, apikey):
        from subprocess import call

        userenv = os.environ.copy()
        userenv["CARINA_USERNAME"]=username
        userenv["CARINA_APIKEY"]=apikey

        result = subprocess.call(["carina", "credentials", "--no-cache", "howtowhale"], env=userenv)
        if(result != 0):
            raise RuntimeError("Unable to download the credentials for the user: {}".format(username))
