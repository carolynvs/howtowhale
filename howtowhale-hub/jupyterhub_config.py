import os

c = get_config()

# Run notebooks in separate container
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.spawner_class = "jupyterhub_carina.CarinaSpawner"
c.DockerSpawner.hub_ip_connect = "howtowhale.com"
c.DockerSpawner.container_prefix = "howtowhale"
c.DockerSpawner.container_image = "carolynvs/howtowhale-user"
c.DockerSpawner.start_timeout = 300
c.DockerSpawner.http_timeout = 300

# Configure oauth
c.Authenticator.admin_users = ["carolynvs"]
c.Authenticator.whitelist = ["carolynvs"]
c.JupyterHub.authenticator_class = "jupyterhub_carina.CarinaAuthenticator"
