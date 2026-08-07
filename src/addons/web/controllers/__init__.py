# Adaptado de Odoo Community `web` (LGPL-3) — DEC-KX-03.
#
# Los módulos se importan aquí para que existan como unidad cargable y el
# gate de sintaxis los alcance. El **ruteo** de cada uno vive en ``urls.py``,
# que hoy publica sólo `database` y `home`: `export`, `json` y `webmanifest`
# se portaron en la partición 1 de :ref:`h-api-371` y su ruteo lo cierra la
# fase de consolidación cuando corra la partición 2.
from addons.web.controllers import database  # noqa: F401
from addons.web.controllers import export  # noqa: F401
from addons.web.controllers import home  # noqa: F401
from addons.web.controllers import json  # noqa: F401
from addons.web.controllers import schema  # noqa: F401
from addons.web.controllers import serializers  # noqa: F401
from addons.web.controllers import session  # noqa: F401
from addons.web.controllers import webmanifest  # noqa: F401
