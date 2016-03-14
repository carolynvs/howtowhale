FROM jupyter/jupyterhub:0.5.0

RUN pip install dockerspawner

ADD lib /tmp/howtowhale-lib
RUN pip install /tmp/howtowhale-lib

CMD ["jupyterhub", "--no-ssl", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
