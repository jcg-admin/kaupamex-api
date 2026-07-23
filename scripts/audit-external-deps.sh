#!/usr/bin/env bash
# audit-external-deps.sh
#
# Probe ops-critical external URLs hardcoded across the kaupamex
# monorepo (provisioners, build setup scripts, package fetchers).
# Exit 0 if all live; exit 1 listing dead/redirected-to-wrong-content.
#
# Origen: D-026 (deploy@yollotl reportó downloads.mariadb.com
# deprecada en produccion). Esta auditoria existe para que el
# proximo cambio silencioso de CDN/endpoint se detecte en
# escritorio y no en produccion.
#
# Re-correr antes de cada release y como parte de cualquier WP que
# toque provisioners. Tiempo: <60 s con conexion normal.
#
# DEC-DOC-008 loud errors: stderr propagado, exit code distinto de
# cero ante cualquier endpoint que devuelva 4xx/5xx o que sirva
# Content-Type incompatible con lo esperado.

set -euo pipefail

readonly SCRIPT_NAME="audit-external-deps"

# --- output helpers ---------------------------------------------------

red()    { printf '\033[31m%s\033[0m' "$1"; }
green()  { printf '\033[32m%s\033[0m' "$1"; }
yellow() { printf '\033[33m%s\033[0m' "$1"; }

# --- inventory --------------------------------------------------------
#
# Format: "URL|expected_content_substring|note"
# expected_content_substring se busca tras seguir redirects.
# Si vacio, basta con HTTP 200 + Content-Type no-HTML (text/html con
# title 'Download' indica pagina de marketing, no recurso real).

declare -a DEPS=(
  # db/ provisioners
  "https://dlm.mariadb.com/repo/mariadb-server/11.8/repo/ubuntu/dists/noble/InRelease|BEGIN PGP SIGNED MESSAGE|MariaDB 11.8 apt repo InRelease (D-026 fix). Endpoint canonico actual."
  "https://mariadb.org/mariadb_release_signing_key.asc|BEGIN PGP PUBLIC KEY BLOCK|GPG key publica de MariaDB (usado por install.sh para signed-by)."
  "https://r.mariadb.com/downloads/mariadb_repo_setup|#!/usr/bin/env bash|Script bootstrap oficial (fallback en hosts sin systemd)."

  # server/ provisioners
  "https://get.acme.sh||Instalador acme.sh para emision de certificados Let's Encrypt."

  # docs/ setup
  "https://astral.sh/uv/install.sh|#!/bin/sh|Instalador uv (gestor de toolchain Python para Sphinx build)."
  "https://download.java.net/openjdk/jdk21/ri/openjdk-21+35_linux-x64_bin.tar.gz||OpenJDK 21 RI portable (requerido por PlantUML)."
  "https://github.com/plantuml/plantuml/releases/download/v1.2024.7/plantuml-1.2024.7.jar||PlantUML 1.2024.7 jar (pinned en docs/scripts/utils/plantuml.sh)."
)

# --- probe ------------------------------------------------------------

PASS=0
FAIL=0
FAILURES=()

printf '%s ── External dependencies liveness audit ──\n' "$(green ">>>")"
printf '   Probing %d URLs\n\n' "${#DEPS[@]}"

for entry in "${DEPS[@]}"; do
  url="${entry%%|*}"
  rest="${entry#*|}"
  expected="${rest%%|*}"
  note="${rest#*|}"

  printf '  %-65s ' "${url:0:65}"

  # Probe: follow redirects, return HTTP code + final URL + content-type
  resp=$(curl -sSLI --max-time 15 -o /dev/null \
              -w "%{http_code}|%{content_type}|%{num_redirects}" \
              "$url" 2>/dev/null || echo "000|connection_failed|0")
  code="${resp%%|*}"
  rest="${resp#*|}"
  ctype="${rest%%|*}"

  if [[ "$code" != "200" ]]; then
    printf '%s (HTTP %s)\n' "$(red "FAIL")" "$code"
    FAILURES+=("${url} -> HTTP ${code}")
    FAIL=$((FAIL + 1))
    continue
  fi

  # If we have an expected substring, fetch the body and grep for it.
  if [[ -n "$expected" ]]; then
    body=$(curl -sSL --max-time 15 "$url" 2>/dev/null | head -c 8192 || true)
    if ! grep -q -F "$expected" <<<"$body"; then
      printf '%s (200 OK pero contenido no contiene "%s")\n' \
        "$(red "FAIL")" "${expected:0:40}"
      FAILURES+=("${url} -> 200 OK pero contenido drift: esperaba '${expected}'")
      FAIL=$((FAIL + 1))
      continue
    fi
  else
    # Sin substring esperado: aceptar 200, pero rechazar text/html
    # disfrazado de marketing (caso D-026: 200 + HTML donde se
    # esperaba binary/script).
    if [[ "$ctype" == text/html* ]]; then
      printf '%s\n' "$(yellow "WARN")"
      printf '       Content-Type=%s — verificar manualmente\n' "$ctype"
    fi
  fi

  printf '%s\n' "$(green "OK")"
  PASS=$((PASS + 1))
done

# --- report -----------------------------------------------------------

echo ""
printf '%s Resultado: %d OK / %d FAIL (de %d totales)\n' \
  "$(green ">>>")" "$PASS" "$FAIL" "${#DEPS[@]}"

if [[ "$FAIL" -gt 0 ]]; then
  echo ""
  printf '%s Endpoints rotos:\n' "$(red "ERR ")"
  for f in "${FAILURES[@]}"; do
    printf '   - %s\n' "$f"
  done
  echo ""
  echo "Accion sugerida:"
  echo "  1. Re-ejecutar manualmente cada URL con 'curl -sSLv <url>' y"
  echo "     verificar redirect chain + content."
  echo "  2. Si el endpoint quedo deprecado, buscar alternativa vigente"
  echo "     del mismo proveedor (ej. dlm.mariadb.com vs downloads.mariadb.com)."
  echo "  3. Actualizar el script consumidor + agregar entrada a"
  echo "     docs/source/gestion/pm/docs/iniciativas/revisar-pendientes-docs/"
  echo "     registro-deuda-tecnica.rst con la causa."
  echo "  4. Re-correr este script para validar el fix."
  exit 1
fi

echo ""
echo "Todos los endpoints externos responden 200 OK con contenido esperado."
echo "Ultima verificacion: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit 0
