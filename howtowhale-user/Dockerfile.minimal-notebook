FROM jupyter/minimal-notebook:8dfd60b729bf

 # Setup the JupyterHub single user entrypoint
 USER root
 RUN wget -q https://raw.githubusercontent.com/jupyter/jupyterhub/master/scripts/jupyterhub-singleuser -O /usr/local/bin/jupyterhub-singleuser && \
     chmod 755 /usr/local/bin/jupyterhub-singleuser && \
     mkdir -p /srv/singleuser/ && \
     wget -q https://raw.githubusercontent.com/jupyter/dockerspawner/master/singleuser/singleuser.sh -O /srv/singleuser/singleuser.sh && \
     chmod 755 /srv/singleuser/singleuser.sh

 # Verify that the JupyterHub entrypoint works
 USER jovyan
 RUN sh /srv/singleuser/singleuser.sh -h

 # Configure the JupyterHub entrypoint
 CMD ["sh", "/srv/singleuser/singleuser.sh"]
