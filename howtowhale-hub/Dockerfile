FROM jupyter/jupyterhub:0.5.0

ARG domain
ARG version

ADD lib /tmp/howtowhale-lib

RUN pip install dockerspawner && \
    pip install /tmp/howtowhale-lib && \
    sed -i "s/DOMAIN/${domain}/g" /srv/jupyterhub/jupyterhub_config.py && \
    sed -i "s/VERSION/${version}/g" /srv/jupyterhub/jupyterhub_config.py

CMD ["jupyterhub", "--debug", "--no-ssl", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
