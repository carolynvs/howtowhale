FROM carolynvs/minimal-notebook:8dfd60b729bf

# Continue image setup
USER root

# Install useful utilities
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Install Bash kernel
RUN pip install bash_kernel && \
    python -m bash_kernel.install

# Workaround bug in pexepct 4.0.1, can remove once they release a new version
ADD https://raw.githubusercontent.com/pexpect/pexpect/master/pexpect/bashrc.sh /opt/conda/lib/python3.4/site-packages/pexpect/

# TODO: Install DVM

# Install Docker client
RUN wget --quiet -O /usr/local/bin/docker https://get.docker.com/builds/Linux/x86_64/docker-1.10.2 && \
    chmod +x /usr/local/bin/docker

#Workaround for https://github.com/getcarina/feedback/issues/31#issuecomment-185523037
#USER jovyan

# Mount swarm certificates from swarm-data (/etc/docker)
RUN mkdir -p /var/run/docker && \
  ln -s /etc/docker/ca.pem /var/run/docker/ca.pem && \
  ln -s /etc/docker/cert.pem /var/run/docker/cert.pem && \
  ln -s /etc/docker/key.pem /var/run/docker/key.pem

ADD TryDocker.ipynb /home/jovyan/work/
