FROM jupyter/jupyterhub:0.4.1

RUN pip install dockerspawner

ADD lib /tmp/howtowhale-lib
RUN pip install /tmp/howtowhale-lib

# workaround jupyterhub bug that hasn't been released yet
# https://github.com/jupyter/jupyterhub/commit/b8d9954c28bb5991a752a36ee3e3c21a86281ed4
ADD login.html /opt/conda/share/jupyter/hub/templates/login.html

# Install Carina cli
RUN wget --quiet -O /usr/local/bin/carina https://download.getcarina.com/carina/latest/Linux/x86_64/carina && \
    chmod +x /usr/local/bin/carina
