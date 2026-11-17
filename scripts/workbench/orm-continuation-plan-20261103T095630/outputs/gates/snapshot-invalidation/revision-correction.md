# Corrección de la revisión de esta evidencia

`persist_gate_evidence.py` se invocó con `git rev-parse HEAD` justo después de
un commit que la admisión de estilo había rechazado, así que el registro de
`99b66cf7` etiqueta este gate con `cdad43ad`, que no contiene el cambio.

Lo que el gate midió de verdad: el árbol de trabajo con la corrección de
caché, que quedó commiteada después como `44ce4bcf`. La única diferencia entre
ese árbol y `44ce4bcf` es de forma, no de conducta:

1. el bloque del reloj de copias se movió al final de `src/orm/environments.py`
   para que la admisión de estilo no contara como nuevas las líneas largas
   heredadas que venían después (su huella incluye la posición en el módulo);
2. `tests/unit/orm/test_environments_transaction.py` declara el slot
   `field_invalidated`, que era el único fallo del gate.

Tras los dos cambios: `60 passed` sobre las tres suites afectadas
(`test_invalidate_drops_instance_snapshot.py`,
`test_environments_transaction.py`, `test_purchase_line_qty_invoiced.py`).
El historial no se reescribe; esta nota es la corrección.
