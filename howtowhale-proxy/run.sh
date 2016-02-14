#!/bin/sh

set -xeu

#echo $HUB_INTERNAL_IP howtowhale-hub >> /etc/hosts

/usr/sbin/nginx -g "daemon off;"
