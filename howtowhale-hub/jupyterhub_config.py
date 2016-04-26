import os

domain = os.getenv('DOMAIN')
version = os.getenv('VERSION')

c = get_config()
c.JupyterHub.db_url = 'mysql://{}:{}@{}:3306/{}'.format(
    os.getenv("DB_USERNAME"), os.getenv("DB_PASSWORD"), os.getenv("DB_HOST"), os.getenv("DB_NAME"))

c.JupyterHub.base_url = "/jupyter"
c.JupyterHub.confirm_no_ssl = True

# Configure JupyterHub to authenticate against Carina
c.JupyterHub.authenticator_class = "jupyterhub_carina.CarinaAuthenticator"
c.CarinaAuthenticator.admin_users = ["carolynvs"]
c.CarinaAuthenticator.oauth_callback_url = "https://{}/jupyter/hub/oauth_callback".format(domain)

# Configure JupyterHub to spawn user servers on Carina
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.spawner_class = "jupyterhub_carina.CarinaSpawner"
c.CarinaSpawner.hub_ip_connect = domain
c.CarinaSpawner.cluster_name = "howtowhale"
c.CarinaSpawner.container_prefix = "howtowhale"
c.CarinaSpawner.container_image = "carolynvs/howtowhale-user:{}".format(version)
c.CarinaSpawner.default_url = "/notebooks/TryDocker.ipynb"

# Debug ALL THE THINGS!
c.JupyterHub.log_level = 'DEBUG'
c.CarinaAuthenticator.debug = True
c.CarinaSpawner.debug = True
c.CarinaOAuthClient.debug = True
