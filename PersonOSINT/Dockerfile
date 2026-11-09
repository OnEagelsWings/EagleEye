# syntax=docker/dockerfile:1
# EagleEye PersonOSINT – Server-Image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    EAGLEEYE_PERSONOSINT_DATA=/data EAGLEEYE_HOST=0.0.0.0 EAGLEEYE_PORT=8380

# Optional: LibreOffice für den PDF/A-Export der Dossiers (WITH_PDF=1, ca. 400 MB zusätzlich)
ARG WITH_PDF=1
RUN if [ "$WITH_PDF" = "1" ]; then apt-get update && apt-get install -y --no-install-recommends libreoffice-writer-nogui fonts-dejavu-core \
      && rm -rf /var/lib/apt/lists/*; fi \
    && useradd --system --uid 10001 --home /data eagleeye

WORKDIR /app
COPY requirements.txt .
# Optional: Firmen-Proxy mit eigener CA ->  docker build --secret id=ca_bundle,src=/pfad/ca.crt .
RUN --mount=type=secret,id=ca_bundle,required=false \
    if [ -f /run/secrets/ca_bundle ]; then export PIP_CERT=/run/secrets/ca_bundle; fi; \
    grep -v -E "^(httpx|pytest)" requirements.txt > req.txt && pip install -r req.txt && rm req.txt
COPY personosint ./personosint

RUN mkdir -p /data /backups && chown eagleeye /data /backups
USER eagleeye
VOLUME ["/data", "/backups"]
EXPOSE 8380
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8380/api/auth/state', headers={'Host':'localhost'}), timeout=4).status==200 else 1)"
CMD ["python", "-m", "personosint", "--no-browser"]
