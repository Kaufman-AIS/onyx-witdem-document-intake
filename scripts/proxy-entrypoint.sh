#!/usr/bin/env bash
set -euo pipefail

CERT_DIR=/certs
KEY="$CERT_DIR/key.pem"
CERT="$CERT_DIR/cert.pem"

if [[ ! -f "$KEY" || ! -f "$CERT" ]]; then
  mkdir -p "$CERT_DIR"
  openssl req -x509 -newkey rsa:2048 \
    -keyout "$KEY" -out "$CERT" \
    -days 825 -nodes \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:::1"
fi

# Port 8080: plain HTTP (host 3001 for scripts; nginx routes host 3000 HTTP here).
# Port 8443: TLS (nginx routes host 3000 HTTPS here).
# Port 3000: nginx stream multiplexer — HTTP and HTTPS on the same host port.
uvicorn witdem_onyx_demo.proxy.app:app --host 0.0.0.0 --port 8080 &
uvicorn witdem_onyx_demo.proxy.app:app \
  --host 127.0.0.1 --port 8443 \
  --ssl-keyfile "$KEY" --ssl-certfile "$CERT" &
nginx -c /app/scripts/nginx-stream.conf -g 'daemon off;' &
wait -n
