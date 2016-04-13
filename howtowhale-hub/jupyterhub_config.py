import os

domain = os.getenv('DOMAIN')
version = os.getenv('VERSION')

c = get_config()
c.JupyterHub.db_url = 'mysql://{}:{}@{}:3306/{}'.format(os.getenv("DB_USERNAME"), os.getenv("DB_PASSWORD"), os.getenv("DB_HOST"), os.getenv("DB_NAME"))

c.JupyterHub.base_url = "/jupyter"
c.JupyterHub.confirm_no_ssl = True

# Run notebooks in separate container
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.spawner_class = "jupyterhub_carina.CarinaSpawner"
c.CarinaSpawner.hub_ip_connect = domain
c.CarinaSpawner.cluster_name = "howtowhale"
c.CarinaSpawner.container_prefix = "howtowhale"
c.CarinaSpawner.container_image = "carolynvs/howtowhale-user:{}".format(version)
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
c.CarinaAuthenticator.oauth_callback_url = "https://{}/jupyter/hub/oauth_callback".format(domain)
