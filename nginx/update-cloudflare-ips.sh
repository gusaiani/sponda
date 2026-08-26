#!/usr/bin/env bash
#
# Regenerate nginx/cloudflare-real-ip.conf from Cloudflare's published ranges.
#
# The generated file is committed rather than fetched at reload time. nginx has
# to be able to start when Cloudflare is unreachable, and a `set_real_ip_from`
# list that silently comes back empty would make every visitor look like the
# same Cloudflare edge address, which is how a shared rate-limit bucket happens.
#
# Cloudflare changes these ranges roughly once a year and announces it. Run this,
# read the diff, commit it. Do not wire it into the deploy.
#
#   ./nginx/update-cloudflare-ips.sh
#
set -euo pipefail

IPV4_SOURCE="https://www.cloudflare.com/ips-v4"
IPV6_SOURCE="https://www.cloudflare.com/ips-v6"

# Cloudflare has published 15 IPv4 and 7 IPv6 ranges for years. A list that came
# back much shorter is a truncated response or a captive portal, not real news.
MINIMUM_IPV4_RANGES=10
MINIMUM_IPV6_RANGES=5

script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_file="${script_directory}/cloudflare-real-ip.conf"

fetch_ranges() {
    local source_url="$1" minimum_count="$2" ranges

    ranges="$(curl --silent --show-error --fail --max-time 20 "${source_url}")"
    local count
    count="$(printf '%s\n' "${ranges}" | grep --count . || true)"
    if [ "${count}" -lt "${minimum_count}" ]; then
        echo "refusing to write: ${source_url} returned ${count} ranges, expected at least ${minimum_count}" >&2
        exit 1
    fi

    while read -r range; do
        [ -n "${range}" ] || continue
        if ! [[ "${range}" =~ ^[0-9a-fA-F:.]+/[0-9]{1,3}$ ]]; then
            echo "refusing to write: ${source_url} returned a malformed range: ${range}" >&2
            exit 1
        fi
        printf 'set_real_ip_from %s;\n' "${range}"
    done <<<"${ranges}"
}

{
    cat <<'HEADER'
# Cloudflare's edge ranges, and the header they use to name the real visitor.
#
# GENERATED FILE. Do not hand-edit: run nginx/update-cloudflare-ips.sh.
#
# Included at *server* scope by sponda.capital.conf, not from conf.d. This box
# fronts eighteen sites and only sponda.capital sits behind Cloudflare; trusting
# these ranges globally would rewrite $remote_addr for the other seventeen too.
#
# What this buys: nginx replaces $remote_addr with CF-Connecting-IP, but only
# when the connection actually came from one of these ranges. A request that
# reaches the origin directly keeps its true peer address no matter what header
# it sends, so the forged value can never reach Django's client_ip().
HEADER
    printf '\n'
    fetch_ranges "${IPV4_SOURCE}" "${MINIMUM_IPV4_RANGES}"
    printf '\n'
    fetch_ranges "${IPV6_SOURCE}" "${MINIMUM_IPV6_RANGES}"
    cat <<'FOOTER'

# Single-valued, so real_ip_recursive would have nothing to walk. Cloudflare
# overwrites this header at the edge on every request, including when the
# visitor sends one of their own.
real_ip_header CF-Connecting-IP;
FOOTER
} >"${output_file}"

echo "wrote ${output_file}"
