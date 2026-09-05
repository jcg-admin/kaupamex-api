```yml
type: Reference (lazy-load on-demand)
applies_when: Se toca SPECTACULAR_SETTINGS, se razona sobre la config global del schema, o se depura un hook de generación
created_at: 2026-07-18 03:41:37
status: Aprobado
version: 1.0.0
source: drf-spectacular settings + config/spectacular_hooks.py
```

# SPECTACULAR_SETTINGS — config global (cerrada) + hooks Open/Closed

> `SPECTACULAR_SETTINGS` (`config/settings/base.py:347`) lleva **solo** config
> global inmutable. Los tags y extensiones **por app** NO viven aquí — los recogen
> dos hooks propios desde el `schema.py` de cada app (patrón Open/Closed).

## Metadatos e identidad

PROVEN 2026-08-12 (`src/config/settings/base.py:493-510`; supersede la
medición 2026-07-18, que citaba `TITLE: 'Kaupamex API'` — decisión de
producto del ejecutor 2026-08-05 lo cambió):

- `TITLE`: `'Kaupamex API'` · `VERSION`: `'1.0.0'` · `LICENSE`: `'Propietario'`.
- `DESCRIPTION`: declara la auth de **sesión** (cookie HttpOnly via
  `POST /api/v2/auth/login/`) y el prefijo `/api/v2/`.
- `CONTACT`: `'Equipo Kaupamex' / 'soporte@kaupamex.com'` — es el **operador L0 de
  la plataforma**, no el buzón del L1 de ejemplo (DEC-KX-05, follow-up #199). El
  `TITLE`/`DESCRIPTION` nombran ahora al operador L0 (Kaupamex): la API es una
  sola y sirve a todas las Company, no sólo a una empresa L1. Guardado por regresión en `tests/integration/test_schema.py`. Ver
  `backend-drf/references/schema.md`.

## Comportamiento del generador

- `SERVE_PUBLIC: True` + `SERVE_PERMISSIONS: ['AllowAny']` — el schema es público.
- `SERVE_INCLUDE_SCHEMA: False` — el propio `/api/schema/` no aparece en el schema.
- `SCHEMA_PATH_PREFIX: r'/api/v[0-9]+'` — recorta el prefijo `/api/vN` al derivar
  operationIds/paths (coherente con el versionado por URL, ver
  `backend-drf/references/versioning.md`).
- `COMPONENT_SPLIT_REQUEST: True` (**no-default** — el default de spectacular es
  `False`) + `COMPONENT_SPLIT_PATCH: True` — request y response se documentan como
  componentes **separados** (los `write_only`/`read_only` no se mezclan; PATCH con
  todos los campos opcionales). Efecto lateral documentado: `COMPONENT_SPLIT_REQUEST`
  activa implícitamente `ENFORCE_NON_BLANK_FIELDS` (los `minLength:1` se modelan bien
  al separar request de response).
- `OAS_VERSION: '3.0.3'` · `SORT_OPERATIONS: True`.
- `SWAGGER_UI_SETTINGS` / `REDOC_UI_SETTINGS` — UI (deepLinking, filter,
  `docExpansion: 'none'`, `persistAuthorization`, etc.).

## Enums

- `ENUM_GENERATE_CHOICE_DESCRIPTION: True` — documenta cada valor del choice.
- `ENUM_SUFFIX: ''` — sin sufijo `Enum` automático en el nombre del componente.
- `ENUM_NAME_OVERRIDES: {...}` — mapa que **fija el nombre** de choice sets que
  colisionan (dos serializers con el mismo choice, o dos choices distintos con el
  mismo nombre de campo). Ver `enum-overrides.md`.

## Defaults heredados — lo que NO se fija (decisión implícita)

Todo lo que no está en el bloque rige por **default de drf-spectacular**. PROVEN
2026-07-18 (0 overrides en `base.py` para cada uno):

- `ENABLE_DJANGO_DEPLOY_CHECK: True` (default) — **la generación del schema corre
  como parte de `manage.py check --deploy`** y emite sus warnings ahí. Es el gate
  de esta capa (ver "Verificación" abajo).
- `SCHEMA_PATH_PREFIX_TRIM: False`, `COMPONENT_NO_READ_ONLY_REQUIRED: False`,
  `ENABLE_LIST_MECHANICS_ON_NON_2XX: False` (las respuestas de error no listan
  paginación), `AUTHENTICATION_WHITELIST: None` (se expone la auth de sesión tal
  cual), `SORT_OPERATION_PARAMETERS: True`, `APPEND_COMPONENTS/SERVERS: {}/[]`.
- **Settings de DRF que drf-spectacular lee** (todos en su default DRF, 0 override):
  `COERCE_DECIMAL_TO_STRING` (→ decimales como **string** también en el schema,
  coherente con `backend-drf/references/serializer-fields.md`), `URL_FORMAT_OVERRIDE`
  / `FORMAT_SUFFIX_KWARG` (`'format'`; ver `backend-drf/references/format-suffixes.md`),
  `SCHEMA_COERCE_PATH_PK: True` (`{pk}`→`{id}` en los paths del schema).

No fijar estos sin una necesidad concreta — cambiar un default global afecta
**todo** el schema.

## Verificación — el gate `check --deploy` (default-ON)

Como `ENABLE_DJANGO_DEPLOY_CHECK` es `True`, el schema se **genera** y sus warnings
se emiten en el deploy check::

    cd /home/user/kaupamex-api && \
      DJANGO_SETTINGS_MODULE=config.settings.testing \
      uv run python manage.py check --deploy 2>&1 | grep -iE "spectacular|schema|W"

Ejecutado 2026-07-18 → **exit 0**, sin warnings de spectacular (schema limpio).
Un `Warning: could not resolve …` señala una extensión faltante; un `multiple
names for the same choice set` señala un enum sin override (`enum-overrides.md`).
Para el schema crudo completo: `manage.py spectacular --file /tmp/schema.yml`
(este último **no** está cableado como gate — correrlo a mano al iterar).

## Los dos hooks propios — Open/Closed (`config/spectacular_hooks.py`)

`SPECTACULAR_SETTINGS` registra hooks que hacen el schema **extensible sin tocar
`base.py`** (PROVEN 2026-07-18):

- **PREPROCESSING** → `register_app_schema_extensions`: importa el `schema.py` de
  cada app propia (`addons.*`/`core`) **antes** de generar. Motivo: las
  extensiones (`OpenApiAuthenticationExtension`, serializer/view) se auto-registran
  vía `__init_subclass__` **al definirse la clase**; si el import ocurre solo en
  postprocesamiento, `CsrfExemptSessionScheme` (cookieAuth, ADR-018) llega tarde y
  drf-spectacular deja el schema **sin** `securityScheme` con un warning por vista.
- **POSTPROCESSING** → `collect_app_tags`: itera las apps, lee `SPECTACULAR_TAGS`
  de cada `schema.py` y los agrega al schema final (dedup por `name`). Si una app
  no tiene `schema.py` o `SPECTACULAR_TAGS`, se ignora en silencio — el hook nunca
  bloquea la generación.

Además de los propios, se conservan los built-in
`postprocess_schema_enums` (PRE `preprocess_exclude_path_format`) de drf-spectacular.

**Por qué NO se usa `AppConfig.ready()` para importar los `schema.py`:** metería un
import dentro de un método → lo bloquea `check_no_lazy_imports`. El PREPROCESSING
hook es la vía sancionada (ver el comentario en `addons/users/apps.py`).

## Reglas al tocar la config

1. **Config global** (título, auth, generador, enum override) → `base.py`, con
   comentario citando el ADR/hallazgo.
2. **Tag o extensión de una app** → su `schema.py`, **nunca** `base.py`
   (Open/Closed).
3. **No** quitar `register_app_schema_extensions` del PREPROCESSING — sin él se
   pierde `cookieAuth` (ADR-018).
4. Un enum que colisiona → `ENUM_NAME_OVERRIDES` (no renombrar el choice del
   modelo por un problema de schema).

## Referencias cruzadas

- (por pieza) `per-app-schema` — el contrato del `schema.py` que los hooks consumen.
- (por pieza) `enum-overrides` — el mapa `ENUM_NAME_OVERRIDES`.
- `backend-drf/references/schema.md` — `DEFAULT_SCHEMA_CLASS` + superficie publicada.
- `backend-drf/references/authentication.md` — la auth de sesión que
  `CsrfExemptSessionScheme` documenta.
- Código: `config/settings/base.py:347` (`SPECTACULAR_SETTINGS`),
  `config/spectacular_hooks.py` (los 2 hooks).
```
