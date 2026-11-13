# Uso: ensure-postgres.sh — deja el cluster 16/main aceptando conexiones.
# Idempotente: si responde, no hace nada. Tras un reinicio del contenedor el
# cluster queda parado; Debian lo opera por cluster (pg_ctlcluster), y el
# éxito se verifica con pg_isready, no con el código del arranque.
# Sale 0 listo, 1 si no responde tras arrancar.
set -u
pg_isready -q && exit 0
echo "ensure-postgres: cluster parado, arrancando ($(date -u +%FT%T))"
sudo pg_ctlcluster 16 main start 2>&1 | tail -2
for _ in $(seq 1 30); do pg_isready -q && { echo "ensure-postgres: listo"; exit 0; }; sleep 1; done
echo "ensure-postgres: no responde tras arrancar"; exit 1
