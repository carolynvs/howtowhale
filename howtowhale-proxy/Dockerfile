FROM nginx

ARG domain

ADD default.conf /etc/nginx/conf.d/default.conf
ADD run.sh /run.sh

RUN sed -i "s/DOMAIN/${domain}/g" /etc/nginx/conf.d/default.conf

CMD ["sh", "-c", "/run.sh"]
