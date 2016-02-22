FROM jupyter/singleuser

# Continue image setup
USER root

# Install Bash kernel
RUN pip install bash_kernel && \
    python -m bash_kernel.install

# Workaround bug in pexepct 4.0.1, can remove once they release a new version
ADD https://raw.githubusercontent.com/pexpect/pexpect/master/pexpect/bashrc.sh /opt/conda/lib/python3.4/site-packages/pexpect/

# Install Docker client
RUN wget --quiet -O /usr/local/bin/docker https://get.docker.com/builds/Linux/x86_64/docker-1.10.0 && \
    chmod +x /usr/local/bin/docker

#Workaround for https://github.com/getcarina/feedback/issues/31#issuecomment-185523037
#USER jovyan

ADD TryDocker.ipynb /home/jovyan/work/
