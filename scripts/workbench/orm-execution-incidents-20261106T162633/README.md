# Incidentes de ejecución de `completar-raiz-orm`

Registro de incidentes de ejecución: ninguno es progreso contractual.

## INC-01 — unidad vacía asentada

El ciclo de `orm-environments-reference-0485` se ejecutó sin su archivo de
inclusión (el comando que lo creaba fue rechazado por el clasificador de la
sesión). `local_plan incorporate` registró la fila con `obligations: []` y
`settle_item` la aceptó en `api@a7063ffb`. No añadió filas de evidencia:
`verified_contracts.tsv` no cambió y el inventario de `environments.py` siguió
en 93 `not_verified`.

La fila y su registro `accepted` se conservan tal cual (el historial no se
reescribe). Las seis obligaciones reales van en
`orm-environments-contracts-reference-0485` (`api@ac0d346d`). El script del
ciclo rehúsa desde entonces una unidad sin obligaciones o un archivo de
inclusión ausente (exit 8).

## INC-02 — publicación del Provider bloqueada

El pre-push de Thyrox (`check-finding-id-unique`) rechaza la rama
`claude/bold-fermat-x2hokp` porque 279 filas del store no tienen su `.rst`
fuera del baseline. Esa deuda es de `TASK-THYROX-1132`. Quedan sin publicar
los commits listados en `outputs/provider-unpublished-commits.tsv`, entre ellos
H-THYROX-704 (el vocabulario prohibido no registra «arnés»).

Corresponde examinarlo a VM-A. No se eluden los hooks, no se toca la autoridad
del TaskStore de Thyrox y ningún commit del Provider entra en el Consumer. El
Consumer sigue admitiendo y ejecutando unidades con los mecanismos
disponibles.

## INC-03 — unidad asentada con un caso sin cubrir

`tools-date-utils-reference-0485` (`api@79503129`) asentó `parse_date`
mientras `_current_timezone` ignoraba la clave `tz` del contexto, que la
fuente lee antes que la del usuario (`odoo19c: odoo/orm/environments.py:285-294`).
La rejilla de dominios lo expuso sólo cuando la fecha UTC y la de Ciudad de
México difirieron. Prueba roja `api@76b29461`, corrección `api@df027b8c`
(H-API-1157).

El candidato correctivo `tools-date-utils-context-tz-0486`
(`outputs/rejected-candidate-tools-date-utils-context-tz-0486.jsonl`) lo
rechazó `local_plan supply` como duplicado: una obligación que ya está en el
plan, aunque esté aceptada, no tiene vía de reapertura. La corrección se hizo
bajo los claims vigentes de `TASK-API-0485`. La vía de reapertura es una
capacidad pendiente del Provider; corresponde a VM-A.
