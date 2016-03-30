FROM jupyter/jupyterhub:0.5.0

ADD lib /tmp/howtowhale-lib
ADD jupyterhub-web /srv/jupyterhub/share/jupyter/hub

# Customize JupyterHub installation
RUN python setup.py js && \
    npm install && \
    pip install --upgrade --no-deps --force-reinstall . && \
    rm -rf node_modules ~/.cache ~/.npm

RUN apt-get update && \
    apt-get install -y libmysqlclient-dev && \
    apt-get autoremove -y && \
    pip install mysqlclient && \
    pip install dockerspawner && \
    pip install /tmp/howtowhale-lib

CMD ["jupyterhub", "--debug", "--no-ssl", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
