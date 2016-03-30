FROM jupyter/jupyterhub:0.5.0

ADD lib /tmp/howtowhale-lib
ADD bootstrap.cerulean.min.css /srv/jupyterhub/share/jupyter/hub/static/components/bootstrap/css/boostrap.min.css

RUN apt-get update && \
    apt-get install -y libmysqlclient-dev && \
    apt-get autoremove -y && \
    pip install mysqlclient && \
    pip install dockerspawner && \
    pip install /tmp/howtowhale-lib

CMD ["jupyterhub", "--debug", "--no-ssl", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
