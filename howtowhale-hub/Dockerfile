FROM jupyter/jupyterhub:0.4.1

RUN pip install dockerspawner oauthenticator

ADD lib /tmp/howtowhale-lib
RUN pip install /tmp/howtowhale-lib
