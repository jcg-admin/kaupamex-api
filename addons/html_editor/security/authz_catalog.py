"""Catálogo L0 que dueña ``html_editor`` — ≙ su ``security/ir.model.access.csv``.

Lo recoge ``seed_authz`` vía ``addons.authz.declaration.discover()``.

Por qué estos códigos son de este addon: sus endpoints crean, leen y borran
``ir.attachment`` **de cualquier registro** (el diálogo de medios del editor),
emiten en el canal de coedición del bus y hablan con servicios externos. Es el
mismo criterio que ``web/security/authz_catalog.py``: el addon que declara la
vista declara también sus derechos de acceso.

Sin esta declaración, los endpoints quedarían gateados por códigos que ningún
rol —ni ``superadmin``— podría tener nunca, y toda petición devolvería 403 sin
excepción: ``seed_authz`` sólo otorga las capacidades que ``discover()``
recolecta.

**Cuatro de las cinco son sensibles**, y por la misma razón que las de ``web``:
son deliberadamente amplias. ``html_editor.attachment.*`` opera sobre adjuntos
de cualquier modelo con un ``res_id`` válido, y ``html_editor.text.generate``
manda el texto del usuario a un servicio externo.

``html_editor.collaboration.use`` **no** es sensible: el canal al que da acceso
lo filtra ``models/ir_websocket.py`` registro a registro, comprobando lectura y
escritura del campo concreto. La capacidad abre la puerta; la guarda de canal
decide qué hay detrás.

Las dos rutas públicas de la fuente —``shape`` e ``image_shape``, que declara
``auth='public'``— no consumen capacidad: van con ``AllowAny`` explícito y
documentado en ``controllers/main.py``.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(code='html_editor', name='Editor de contenido enriquecido',
               category='Platform'),
]

CAPABILITIES = [
    CapabilitySpec(
        code='html_editor.attachment.view',
        name='Leer la información de un adjunto desde el editor',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='html_editor.attachment.create',
        name='Subir o modificar un adjunto desde el editor',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='html_editor.attachment.remove',
        name='Borrar un adjunto que ninguna vista use',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='html_editor.collaboration.use',
        name='Emitir y recibir pasos de coedición de un campo HTML',
        is_sensitive=False,
    ),
    CapabilitySpec(
        code='html_editor.text.generate',
        name='Generar texto con el servicio externo del editor',
        is_sensitive=True,
    ),
]
