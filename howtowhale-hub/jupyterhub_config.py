import os

c = get_config()

# Run notebooks in separate container
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.spawner_class = "jupyterhub_carina.CarinaSpawner"
c.CarinaSpawner.hub_ip_connect = "howtowhale.com"
c.CarinaSpawner.container_prefix = "howtowhale"
c.CarinaSpawner.container_image = "carolynvs/howtowhale-user"
c.CarinaSpawner.start_timeout = 300
c.CarinaSpawner.http_timeout = 300

# Configure oauth
c.Authenticator.admin_users = ["carolynvs"]
c.JupyterHub.authenticator_class = "jupyterhub_carina.CarinaAuthenticator"
c.CarinaAuthenticator.oauth_callback_url = "https://howtowhale.com/hub/oauth_callback"
c.CarinaAuthenticator.client_id = os.environ["CARINA_CLIENT_ID"]
c.CarinaAuthenticator.client_secret = os.environ["CARINA_CLIENT_SECRET"]
