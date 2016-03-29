import os

c = get_config()
c.JupyterHub.db_url = 'mysql://jupyterhub:{}@{}:3306/jupyterhub'.format(os.getenv("DB_PASSWORD"), os.getenv("DB_HOST"))

c.JupyterHub.base_url = "/jupyter"
c.JupyterHub.confirm_no_ssl = True

# Run notebooks in separate container
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.spawner_class = "jupyterhub_carina.CarinaSpawner"
c.CarinaSpawner.hub_ip_connect = "DOMAIN"
c.CarinaSpawner.container_prefix = "howtowhale"
c.CarinaSpawner.container_image = "carolynvs/howtowhale-user:VERSION"
c.CarinaSpawner.start_timeout = 300

# Debug ALL THE THINGS!
c.JupyterHub.log_level = 'DEBUG'
c.JupyterHub.admin_access = True
c.Spawner.debug = True
c.DockerSpawner.debug = True
c.CarinaSpawner.debug = True
c.Spawner.args = ['--debug', '--NotebookApp.default_url=/notebooks/TryDocker.ipynb']

# Configure oauth
c.Authenticator.admin_users = ["carolynvs"]
c.JupyterHub.authenticator_class = "jupyterhub_carina.CarinaAuthenticator"
c.CarinaAuthenticator.oauth_callback_url = "https://DOMAIN/hub/oauth_callback"
c.CarinaAuthenticator.client_id = os.environ["CARINA_CLIENT_ID"]
c.CarinaAuthenticator.client_secret = os.environ["CARINA_CLIENT_SECRET"]
