FROM nginx:1.25.5-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d
COPY cert.crt /etc/nginx/conf.d
COPY cert.key /etc/nginx/conf.d
