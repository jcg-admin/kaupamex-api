# /hh.bak: origen, y por qué se conserva

Medido el 2026-11-15T19:20:25:

- Propietario root, 7064 bytes, mtime 2026-11-14 14:52:56 UTC.
  `fuser /hh.bak`: ningún proceso lo tiene abierto.
- Origen: lo escribió esta sesión. Línea 100050 del transcript
  0390150a-c498-513f-9c46-273b863ccf3b, durante la anulación de
  `hr_homeworking`: `cp $F $S/hh.bak 2>/dev/null || cp $F
  <scratchpad>/hh.bak`. `$S` no estaba definido, así que el primer
  `cp` escribió en `/hh.bak`.
- Contenido: copia de trabajo, sin commitear, de
  `addons/hr_homeworking/models/hr_homeworking.py`. md5
  8e3f5db22cac0c28cedaa7adb1a4b8e3. No coincide con ninguna revisión
  commiteada: frente a 7d3e9af4, HEAD del archivo, difiere en 36 líneas,
  sólo de docstring.
- Riesgo de retirarlo: ninguno medido. Es una copia intermedia y la versión
  vigente está en git.
- Estado: **se conserva.** La comprobación de seguridad del cliente rechaza
  cualquier `rm` sobre una ruta de la raíz del sistema de archivos
  (`rm -- /hh.bak`, 2026-11-15), y sólo una persona puede aprobarlo. No
  se elude.
