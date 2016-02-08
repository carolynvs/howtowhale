import os

c = get_config()

# Run notebooks in separate container
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"
c.DockerSpawner.tls_verify = True
c.DockerSpawner.tls_ca = "/etc/docker/ca.pem"
c.DockerSpawner.tls_cert = "/etc/docker/server-cert.pem"
c.DockerSpawner.tls_key = "/etc/docker/server-key.pem"
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.hub_ip_connect = "howtowhale.com"
c.DockerSpawner.container_prefix = "howtowhale"
c.DockerSpawner.container_image = "carolynvs/howtowhale-user"

# Configure oauth
c.JupyterHub.login_url = "/hub/oauth_login"
c.Authenticator.admin_users = ["carolynvs"]
c.JupyterHub.authenticator_class = "jupyterhub_carina.CarinaAuthenticator"
c.CarinaAuthenticator.oauth_callback_url = "http://howtowhale.com/hub/oauth_callback"
c.CarinaAuthenticator.client_id = os.environ["GITHUB_CLIENT_ID"]
c.CarinaAuthenticator.client_secret = os.environ["GITHUB_CLIENT_SECRET"]
