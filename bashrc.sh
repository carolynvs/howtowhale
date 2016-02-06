# Manually copy this until pexpect releases this fix
# https://github.com/pexpect/pexpect/issues/305
source /etc/bash.bashrc
source ~/.bashrc

# Reset PS1 so pexpect can find it
PS1="$"
