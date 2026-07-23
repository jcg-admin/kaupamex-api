"""``security`` — fiel a ``odoo/service/security.py`` (Odoo 19).

En Odoo ``service/security.py`` gestiona la **integridad de la sesión**:
``compute_session_token(session, env)`` deriva un token HMAC a partir de datos del
usuario (password hash, sid, etc.), y ``check_session(session, env, request)``
valida que la sesión siga siendo legítima (evita secuestro tras cambio de
credenciales). Es el guardián a nivel de transporte, distinto de las reglas de
acceso a datos (``ir.rule`` / grupos).

Mapeo a la pila — stub delgado documentado; la seguridad de sesión + autorización
ya está cubierta, en dos capas separadas:

===================================  ===================================================
Odoo ``service/security``            Equivalente en la pila
===================================  ===================================================
``compute_session_token`` (HMAC de   framework de sesiones de Django
sesión)                              (``django_session`` + ``SECRET_KEY``) y/o JWT
                                     firmado (simplejwt); el JWT vive en memoria de
                                     módulo en el UI (DEC-AUTH-2), no en storage (XSS)
``check_session`` (revalidar sesión)  autenticación DRF por request
                                     (``SessionAuthentication`` / ``JWTAuthentication``);
                                     ``invalidate_all_sessions`` invalida el resto de
                                     sesiones tras cambio de credenciales
autorización (a qué puede acceder)   **fuera de este módulo**: ``HasCapability``
                                     fail-closed por vista (DEC-11 niveles L0/L1/L3) +
                                     record rules ``AccessRule`` (DEC-KX-02)
===================================  ===================================================

Por qué stub: Django+DRF ya firman y revalidan la sesión/JWT por request; recrear
el HMAC de sesión duplicaría ``SECRET_KEY``+simplejwt. La **autorización** (lo que
Odoo reparte entre ``security`` y ``ir.rule``) aquí es el modelo de capacidades por
vista, no un token — ver skill ``backend-drf`` y ADR-021 / DEC-KX-02.
"""
