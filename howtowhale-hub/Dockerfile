FROM jupyter/jupyterhub:0.4.1

RUN pip install dockerspawner

ADD lib /tmp/howtowhale-lib
RUN pip install /tmp/howtowhale-lib

# Install Carina cli
RUN wget --quiet -O /usr/local/bin/carina https://download.getcarina.com/carina/latest/Linux/x86_64/carina && \
    chmod +x /usr/local/bin/carina
