"""``common`` — fiel a ``odoo/service/common.py`` (Odoo 19).

En Odoo ``common`` expone los endpoints RPC "comunes" (fuera de un modelo):
``exp_login`` / ``exp_authenticate`` (autenticación → uid), ``exp_version`` /
``exp_about`` (versión del servidor), ``exp_set_loglevel``, y el ``dispatch`` que
enruta el método RPC. Es la cara XML-RPC/JSON-RPC del servidor.

Mapeo a Django/DRF — **la pila DRF ya provee cada pieza**, por eso es un stub
delgado documentado (mismo criterio que los stubs de motor del ORM):

==================================  ===================================================
Odoo ``common``                     Equivalente en la pila
==================================  ===================================================
``exp_login`` / ``exp_authenticate``  autenticación DRF: JWT
                                    (``TokenObtainPairView`` de simplejwt) o sesión
                                    Django; el token vive en memoria de módulo en el
                                    UI (DEC-AUTH-2), no en storage
``exp_version`` / ``exp_about``     endpoint de versión propio / metadata del build;
                                    no se expone un RPC de versión de servidor
``exp_set_loglevel``                config ``LOGGING`` de Django (settings) / admin;
                                    no por RPC en caliente
``dispatch(method, params)``        enrutamiento de URLs de DRF (``urls.py`` +
                                    routers) — no hay dispatcher RPC central
==================================  ===================================================

No hay endpoint RPC genérico: la API es REST (DRF), versionada por URL, y la
autenticación es JWT/sesión. Recrear el ``dispatch`` común duplicaría el router de
DRF. Un cliente que en Odoo llamaba ``common.login`` aquí hace ``POST`` al
endpoint de token; ``common.version`` no aplica.
"""
