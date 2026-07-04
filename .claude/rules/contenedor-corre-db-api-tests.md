```yml
type: Regla de Proyecto
category: Operación del agente — verificación de tests en el contenedor
version: 1.0.0
created_at: 2026-06-02T22:01:00
applies_to: e-comerce v1.0.0+
```

# El contenedor SÍ corre db+api tests — intentar antes de negar

> Cargado automáticamente en cada sesión.
> Caso particular de `react-verification-gate.md`: una afirmación de
> incapacidad ("no puedo correr los tests aquí") es una afirmación de
> estado y NO puede provenir de la distribución del LLM ni de una
> lección heredada — debe derivarse de un intento real ejecutado en
> este turno.

## Regla principal

**Antes de afirmar "no se pueden correr los tests db+api en este
contenedor", INTENTARLO.** El contenedor del agente **SÍ puede** correr
la pila db+api por socket Unix. Negarlo sin intentarlo es un over-claim
del `react-verification-gate.md` (afirmar el resultado *esperado* —
"esto no anda aquí" — como si fuera el resultado *observado*).

Origen del defecto que esta regla corrige: el agente asumía que el
contenedor no era capaz, citando "L-010: contenedor no autoritativo".
Eso confunde **autoridad canónica** con **capacidad** (ver abajo). El
contenedor no es autoritativo para sellar el verde oficial, pero sí es
capaz de ejecutar los tests para verificación rápida.

## Procedimiento PROVEN

Verificado esta sesión (2026-06-02). Comandos exactos:

```bash
# 1. Levantar MariaDB por socket (idempotente)
bash /home/user/e-comerce/db/scripts/start_db.sh

# 2. (opcional) Confirmar que la conexión usa socket, no TCP
cd /home/user/e-comerce-api && \
  PYTHONPATH=practicayoruba DJANGO_SETTINGS_MODULE=config.settings.testing \
  python -c "from django.db import connection; \
    print('unix_socket:', connection.settings_dict.get('OPTIONS',{}).get('unix_socket','<NONE>'))"
# Esperado: unix_socket: /run/mysqld/mysqld.sock

# 3. Correr la suite api contra MariaDB real
cd /home/user/e-comerce/api && \
  uv run pytest tests/integration/cart/test_cart.py --reuse-db
```

Evidencia observada en este turno:

- `start_db.sh` levanta MariaDB 11.8 por socket `/run/mysqld/mysqld.sock`.
- El gate de conexión imprime `unix_socket: /run/mysqld/mysqld.sock`.
- `uv run pytest tests/integration/cart/test_cart.py --reuse-db` →
  **26 passed in 7.40s**.

## Gotchas del entorno (ya corregidos en start_db.sh)

Estos eran los obstáculos que hacían *parecer* que el contenedor no
podía correr los tests. Ya están resueltos en `db/scripts/start_db.sh`
(db@f8b32ba):

1. **`TMPDIR` no escribible por `mysql`.** El contenedor tiene
   `TMPDIR=/tmp/claude-0`, que el usuario `mysql` no puede escribir →
   InnoDB aborta con `Can't create temporary file, Errcode 13`. Fix:
   `start_db.sh` arranca `mariadbd` con `--tmpdir=/tmp`.
2. **MariaDB 11.8 usa `mariadb-admin`, no `mysqladmin`.** El binario
   `mysqladmin` puede no estar presente; `start_db.sh` ya usa
   `mariadb-admin` para los probes de readiness.

Si `start_db.sh` falla, revisar estos dos puntos antes de concluir
"no se puede".

## Capacidad vs autoridad canónica (no contradice L-010)

| Dimensión | Contenedor del agente | WSL / CI |
|---|---|---|
| **Capacidad** (¿puede ejecutar db+api?) | SÍ (PROVEN arriba) | SÍ |
| **Autoridad canónica** (¿sella el verde oficial?) | NO | SÍ (L-010) |

El verde "oficial" de la suite se sella en WSL/CI. El contenedor es un
entorno de **verificación rápida** válido: sirve para detectar
regresiones temprano y para no bloquearse afirmando falsamente que "aquí
no corre nada". Esta regla **no contradice L-010** — la complementa: L-010
fija *dónde* se firma el resultado autoritativo; esta regla fija que la
*capacidad* de correr existe y debe usarse antes de declarar incapacidad.

## Caveats — NO verificados aún en el contenedor

No extender el claim PROVEN de db+api a estos sin verificarlos primero:

- **ui / jest:** el contenedor tiene Node v22, NO el v20 fijado en
  `.nvmrc` (ver `test-execution-protocol.md`, gate de versión de Node /
  L-012). Verificar la versión y el comportamiento ANTES de afirmar que
  jest pasa aquí. No declarar verde de ui sin intentarlo bajo la
  toolchain correcta.
- **E2E de navegador (Playwright):** los browsers de Playwright no están
  confirmados como instalados en este contenedor. NO afirmar que el E2E
  pasa hasta verificar la disponibilidad de los browsers y correrlo.

Estos dos quedan en estado DESCONOCIDO hasta intentarlos — aplica el
mismo principio: intentar antes de afirmar (en cualquier dirección).

## Supersede

Esta regla **supersede la sección "Estado conocido de este entorno"** de
`/home/user/e-comerce-api/.claude/rules/db-conexion-socket.md`, que
declara `unix_socket: <NONE>` (TCP fallback) como estado del entorno. Ese
snapshot (2026-05-29) quedó **obsoleto**: tras el fix de `--tmpdir` en
`start_db.sh`, el contenedor levanta MariaDB por socket y el gate de
conexión da `unix_socket: /run/mysqld/mysqld.sock`. No editar aquí ese
archivo del submódulo `api`; solo se referencia el supersede.

## Severidad

**MEDIA** — sin esta regla, el agente reincide en negar la capacidad del
contenedor y se bloquea o degrada a "no verificable" tareas que sí podía
verificar localmente. No es bloqueante para el flujo, pero su ausencia
reintroduce un over-claim que contradice el `react-verification-gate.md`.

## Relación con otras reglas

- `react-verification-gate.md`: esta regla es un caso particular — la
  incapacidad es una afirmación de estado que requiere intento real.
- `test-execution-protocol.md`: define los comandos canónicos por capa y
  el gate de Node v20 para ui (relevante al caveat de jest).
- `db-conexion-socket.md` (submódulo api): supersedida en su sección
  "Estado conocido de este entorno".
