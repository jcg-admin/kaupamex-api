# Adaptado de Odoo Community `web` (LGPL-3) — DEC-KX-03.
#
# Los módulos se importan aquí para que existan como unidad cargable y el
# gate de sintaxis los alcance. El **ruteo** de cada uno vive en ``urls.py``:
# ``database``, ``home`` y ``session`` publican rutas; ``binary`` publica
# ``content_common``/``content_image``/``upload_attachment``/``company_logo``
# (H-API-369, DEC-FW-04); ``export``, ``json``, ``schema``, ``serializers`` y
# ``webmanifest`` no publican rutas propias (soporte de otros controladores o
# ausentes por diseño); ``utils`` es utilería sin ruta — su único símbolo
# portado (``is_user_internal``) no tiene consumidor todavía: ``home.py``
# declara AUSENTE al único llamador de la referencia (``_login_redirect``,
# ver docstring de ``home.py``); ``webclient`` no expone rutas — ver su
# propio docstring.
from addons.web.controllers import binary  # noqa: F401
from addons.web.controllers import database  # noqa: F401
from addons.web.controllers import export  # noqa: F401
from addons.web.controllers import home  # noqa: F401
from addons.web.controllers import json  # noqa: F401
from addons.web.controllers import schema  # noqa: F401
from addons.web.controllers import serializers  # noqa: F401
from addons.web.controllers import session  # noqa: F401
from addons.web.controllers import utils  # noqa: F401
from addons.web.controllers import webclient  # noqa: F401
from addons.web.controllers import webmanifest  # noqa: F401
