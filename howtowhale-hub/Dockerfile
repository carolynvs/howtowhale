FROM jupyter/jupyterhub:0.5.0

# Install MySQL dependency
RUN apt-get update && \
    apt-get install -y libmysqlclient-dev && \
    apt-get autoremove -y && \
    pip install mysqlclient

# Install jupyterhub-carina plugin
ADD requirements.txt /tmp
RUN pip install -U -r /tmp/requirements.txt

# Customize JupyterHub installation
ADD jupyterhub-web /srv/jupyterhub/share/jupyter/hub
RUN python setup.py js && \
    npm install && \
    pip install --upgrade --no-deps --force-reinstall . && \
    rm -rf node_modules ~/.cache ~/.npm

CMD ["jupyterhub", "--debug", "--no-ssl", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
