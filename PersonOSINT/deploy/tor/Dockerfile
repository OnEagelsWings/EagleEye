# Tor als HTTP-CONNECT-Ausgang für EagleEye (OPSEC-Stufe 2/3)
FROM alpine:3.20
RUN apk add --no-cache tor
COPY torrc /etc/tor/torrc
USER tor
EXPOSE 9080
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s CMD nc -z 127.0.0.1 9080 || exit 1
CMD ["tor", "-f", "/etc/tor/torrc"]
