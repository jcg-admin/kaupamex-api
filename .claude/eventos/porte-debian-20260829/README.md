# Sonda del anclaje al lock — H-API-893

Fecha: 2026-08-29T02:32:44 · repo: kaupamex-api · rama: feature/kaupamex-l2

## Qué se midió

Si `pip install -e .` respeta `uv.lock`. **No lo respeta**: resuelve desde el
índice público contra los rangos abiertos de `pyproject.toml`.

| paquete | pyproject | uv.lock | `pip install -e .` | `--no-deps -r export` |
|---|---|---|---|---|
| Pillow | `>=10.3.0` | 12.2.0 | 12.3.0 | **12.2.0** |
| gunicorn | `>=23.0.0` | 26.0.0 | 26.2.0 | **26.0.0** |
| cryptography | `>=42.0.0` | 48.0.0 | 50.0.1 | **48.0.0** |
| lxml | `>=6.1.1` | 6.1.1 | 6.1.2 | **6.1.1** |

## Archivos

- `requirements.lock.txt` — el export del lock (`uv export --frozen --no-dev
  --no-emit-project`), 49 paquetes con hashes. Es **evidencia fechada**, no el
  artefacto de construcción: ése lo produce `debian/rules` en cada build.
- `subconjunto.txt` — los cuatro paquetes que driftearon, extraídos **por
  bloque**. El primer intento usó `grep -A3`, que truncaba la lista de hashes
  y hacía que pip rechazara por hash — fallo del instrumento, no del método.
- `pip-list-sonda.txt` / `versiones-instaladas.txt` — la salida de la sonda.
- `salida-pip.txt` — la salida cruda de la instalación.

El entorno virtual de la sonda **no se versiona**: es un artefacto
reproducible con binarios, y su valor probatorio ya está en los tres archivos
de salida. Se reconstruye con los dos comandos de arriba.

## Interpretación

Ver `docs: .../empaquetar-kaupamex-bin-como-ejecutable/hallazgos/hallazgo-H-API-893-*.rst`.
