FROM jupyter/jupyterhub:0.5.0

# Install dependencies
RUN apt-get update && \
    apt-get install -y libmysqlclient-dev && \
    apt-get autoremove -y && \
    pip install mysqlclient && \
    pip install dockerspawner

# Customize JupyterHub installation
ADD jupyterhub-web /srv/jupyterhub/share/jupyter/hub
RUN python setup.py js && \
    npm install && \
    pip install --upgrade --no-deps --force-reinstall . && \
    rm -rf node_modules ~/.cache ~/.npm

# Install howtowhale
ADD lib /tmp/howtowhale-lib
RUN pip install /tmp/howtowhale-lib

CMD ["jupyterhub", "--debug", "--no-ssl", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
