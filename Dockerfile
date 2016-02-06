FROM jupyter/notebook

# Install Bash kernel
RUN pip3 install bash_kernel && \
    python3 -m bash_kernel.install

# Workaround bug in pexepct 4.0.1, can remove once they release a new version
ADD bashrc.sh /usr/local/lib/python3.4/dist-packages/pexpect/

# Install docker client
RUN curl -o /usr/local/bin/docker https://get.docker.com/builds/Linux/x86_64/docker-1.10.0 && \
    chmod +x /usr/local/bin/docker
