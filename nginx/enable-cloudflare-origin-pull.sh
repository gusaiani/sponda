#!/usr/bin/env bash
#
# Turn on Authenticated Origin Pulls for sponda.capital. Run on the box, as root.
#
#   ssh root@poe.ma
#   /opt/sponda/nginx/enable-cloudflare-origin-pull.sh
#
# What it does: installs Cloudflare's origin-pull CA and writes the snippet that
# sponda.capital.conf already wildcard-includes, so nginx demands a client
# certificate during the TLS handshake. Cloudflare presents one. Nobody else
# has one. A connection straight to the origin IP is refused before it can send
# a request, which is the only way to stop someone who knows the address from
# walking around the WAF, the rate limits, and the cache.
#
# ORDER MATTERS. Cloudflare only presents that certificate when the zone setting
# is on. Reloading nginx with verification enabled while the zone setting is off
# rejects every real visitor. So the script refuses to reload until you confirm
# the dashboard toggle, and it prints how to back out.
#
set -euo pipefail

ORIGIN_PULL_CA_URL="https://developers.cloudflare.com/ssl/static/authenticated_origin_pull_ca.pem"
CA_PATH="/etc/nginx/cloudflare-origin-pull-ca.pem"
SNIPPET_PATH="/etc/nginx/snippets/sponda-origin-pull.conf"
EXPECTED_CA_SUBJECT_CN="origin-pull.cloudflare.net"

if [ "$(id -u)" -ne 0 ]; then
    echo "run as root: this writes to /etc/nginx and reloads the service" >&2
    exit 1
fi

echo "==> fetching Cloudflare's origin-pull CA"
temporary_ca="$(mktemp)"
trap 'rm -f "${temporary_ca}"' EXIT
curl --silent --show-error --fail --max-time 20 "${ORIGIN_PULL_CA_URL}" -o "${temporary_ca}"

# A captive portal or an error page would also arrive with exit code 0 under
# --fail's narrower definition of failure. Verify it parses and is the right CA.
if ! openssl x509 -in "${temporary_ca}" -noout -subject | grep -q "CN *= *${EXPECTED_CA_SUBJECT_CN}"; then
    echo "refusing to install: ${ORIGIN_PULL_CA_URL} did not return the ${EXPECTED_CA_SUBJECT_CN} certificate" >&2
    exit 1
fi
openssl x509 -in "${temporary_ca}" -noout -subject -enddate

install -m 644 "${temporary_ca}" "${CA_PATH}"
echo "==> installed ${CA_PATH}"

echo
echo "Before reloading, the zone setting has to be on, or every visitor gets a 400:"
echo "  Cloudflare dashboard -> sponda.capital -> SSL/TLS -> Origin Server"
echo "  -> Authenticated Origin Pulls -> on"
echo "  (and confirm SSL/TLS -> Overview is set to Full (strict), not Full)"
echo
read -r -p "Is Authenticated Origin Pulls ON for the sponda.capital zone? [yes/N] " confirmation
if [ "${confirmation}" != "yes" ]; then
    echo "stopping. ${CA_PATH} is installed but unused; nothing has changed for visitors."
    exit 0
fi

mkdir -p "$(dirname "${SNIPPET_PATH}")"
cat >"${SNIPPET_PATH}" <<SNIPPET
# Authenticated Origin Pulls for sponda.capital.
#
# Written by nginx/enable-cloudflare-origin-pull.sh. sponda.capital.conf picks
# this up through a wildcard include, so deleting this file and reloading nginx
# is the rollback.
ssl_client_certificate ${CA_PATH};
ssl_verify_client on;
SNIPPET
echo "==> wrote ${SNIPPET_PATH}"

echo "==> validating"
if ! nginx -t; then
    rm -f "${SNIPPET_PATH}"
    echo "config did not validate; removed ${SNIPPET_PATH} and left nginx running as it was" >&2
    exit 1
fi

systemctl reload nginx
echo "==> reloaded"

echo
echo "Verify. Through Cloudflare, this should still be 200:"
echo "  curl -sS -o /dev/null -w '%{http_code}\\n' https://sponda.capital/api/health/"
echo "Direct to the origin, the handshake should now fail rather than answer:"
echo "  curl -k --resolve sponda.capital:443:127.0.0.1 https://sponda.capital/api/health/"
echo
echo "Roll back with: rm ${SNIPPET_PATH} && nginx -t && systemctl reload nginx"
