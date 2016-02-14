import os
from tornado import gen, web
from jupyterhub.auth import Authenticator
import logging

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

    def create_user_cluster(self, username, apikey):
        from subprocess import call

        userenv = os.environ.copy()
        userenv["CARINA_USERNAME"]=username
        userenv["CARINA_APIKEY"]=apikey
        call(["carina", "create", "--wait", "howtowhale"], env=userenv)

    @gen.coroutine
    def authenticate(self, handler, data):
        username = data['username']
        apikey = data['apikey']

        if(self.authenticate_to_carina(username, apikey)):
            return username

        return None

    def authenticate_to_carina(self, username, apikey):
        return self.list_clusters(username, apikey) == 0

    def list_clusters(self, username, apikey):
        from subprocess import call

        userenv = os.environ.copy()
        userenv["CARINA_USERNAME"]=username
        userenv["CARINA_APIKEY"]=apikey

        return call(["carina", "ls"], env=userenv)
