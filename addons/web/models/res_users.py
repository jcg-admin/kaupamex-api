"""``res.users`` extendido por ``web`` — orden del autocompletado y captcha
de login (Odoo ``web``).

Adaptación de ``odoo19c: addons/web/models/res_users.py``
(``odoo-tools@622ddc2aa5``, 36 líneas, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). Extiende ``res.users`` (ya portado en
``base/models/res_users.py``) con dos cosas del cliente web: el orden del
``name_search`` que alimenta los widgets de autocompletado (el usuario que
busca aparece primero), y si un login concreto exige captcha.

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)`` +
constantes de módulo, mismo criterio que ``porte-completo-no-parcial.md``):
**1** constante (``SKIP_CAPTCHA_LOGIN``) + **3** métodos (``name_search``,
``_on_webclient_bootstrap``, ``_should_captcha_login``). **4 portados, 0
ausentes.**

Divergencias de mecanismo declaradas
=====================================

- ``Domain`` (``odoo.fields.Domain``) → ``Q`` de Django. Este árbol no porta
  la clase ``Domain`` de Odoo (``orm/fields_relational.py`` documenta que el
  ``One2many`` tampoco se porta como clase propia; el patrón se repite: los
  primitivos de dominio dinámico de Odoo no tienen equivalente 1:1, se usa
  el ORM nativo de Django).
- ``self.env.uid`` (usuario que ejecuta la búsqueda, implícito en el
  contexto de Odoo) → parámetro explícito ``current_user_id``. DRF no tiene
  un contexto de sesión implícito equivalente a ``env``; el llamador
  (controller) sabe qué usuario pide el autocompletado y lo declara — mismo
  patrón que ``actor=None`` en
  ``bus/models/res_users_settings.py::settings_channel``.
- ``super().name_search(...)`` no existe: ``base.ResUsers`` no define
  ``name_search`` — es una búsqueda de framework (ilike sobre el nombre
  visible) que este árbol no tenía todavía. Se construye aquí mismo, sobre
  ``login``/``partner__name`` (los dos componentes de
  ``ResUsers.name``/``get_full_name``), en vez de asumir un mecanismo que
  el ORM de Django no tiene. El grueso de la gramática de operadores de
  dominio de Odoo (``=``, ``!=``, ``in``, ``not ilike``…) no se reconstruye
  aquí — no hay consumidor en este árbol todavía (``grep -rn "name_search"
  src/`` → 0 antes de este archivo) y es un motor de consultas aparte, no
  una pieza de este porte puntual; se documenta como alcance abierto, no
  como recorte silencioso.
- ``request``/``request.env.context`` (proxy global de Odoo) → parámetro
  explícito ``skip_captcha_login``. DRF no tiene threadlocal de request; el
  controller que ya validó la identidad por otra vía (p. ej. reautenticación
  tras OAuth) lo declara pasando el centinela ``SKIP_CAPTCHA_LOGIN``
  explícitamente, en vez de leerlo de un contexto implícito.
- ``self.ensure_one()`` en ``_on_webclient_bootstrap`` no se porta como
  aserción: una instancia Django **es siempre** una sola fila (no hay
  recordset de N), así que no hay nada que el guard pueda atrapar aquí.
"""
from orm.method_chain import chain_method

import models
from addons.base.models.res_users import ResUsers

#: Centinela de contexto — ≙ ``SKIP_CAPTCHA_LOGIN`` de la referencia
#: (odoo19c: web/models/res_users.py:7). El llamador lo pasa explícito a
#: ``_should_captcha_login`` para distinguir "omitir captcha a propósito" de
#: un booleano ``False`` corriente.
SKIP_CAPTCHA_LOGIN = object()


def name_search(cls, name='', q=None, operator='ilike', limit=100,
                 current_user_id=None):
    """≙ ``name_search`` (odoo19c: web/models/res_users.py:13-28).

    Busca por ``login`` o por el nombre del partner (equivalente a
    ``ResUsers.name``/``get_full_name``, que delegan en el partner — ver
    ``base/models/res_users.py``). Si ``current_user_id`` aparece entre los
    resultados, se mueve al frente; si no aparece y el límite se llenó, se
    repite la misma búsqueda acotada a ese usuario para confirmar que
    también cumple el filtro (mismo comportamiento de la referencia, ver la
    sección de divergencias del docstring del módulo).
    """
    queryset = cls.objects.select_related('partner').all()
    if q is not None:
        queryset = queryset.filter(q)
    if name:
        queryset = queryset.filter(
            models.Q(login__icontains=name)
            | models.Q(partner__name__icontains=name)
        )
    if limit is not None:
        queryset = queryset[:limit]
    user_list = [(user.pk, user.name) for user in queryset]

    if current_user_id is None:
        return user_list

    index = next(
        (i for i, (user_id, _name) in enumerate(user_list)
         if user_id == current_user_id),
        None,
    )
    if index is not None:
        # index 0 es válido (no falsy): se usa None para no ignorarlo.
        user_tuple = user_list.pop(index)
        user_list.insert(0, user_tuple)
    elif limit is not None and len(user_list) == limit:
        extra_qs = cls.objects.select_related('partner').filter(
            pk=current_user_id)
        if q is not None:
            extra_qs = extra_qs.filter(q)
        if name:
            extra_qs = extra_qs.filter(
                models.Q(login__icontains=name)
                | models.Q(partner__name__icontains=name)
            )
        extra = extra_qs.first()
        if extra is not None:
            user_list = [(extra.pk, extra.name), *user_list[:-1]]
    return user_list


def _on_webclient_bootstrap(self):
    """≙ ``_on_webclient_bootstrap`` (odoo19c: web/models/res_users.py:30-31).

    Punto de extensión vacío que otros addons pueden colgar (via
    ``chain_method``) al arrancar el webclient. Ver la sección de
    divergencias del docstring del módulo — ``ensure_one()`` no se porta
    como aserción.
    """
    return None


def _should_captcha_login(self, credential, skip_captcha_login=False):
    """≙ ``_should_captcha_login`` (odoo19c: web/models/res_users.py:33-36).

    Sólo los logins por password piden captcha — un login por OAuth/SSO ya
    tiene su propia defensa contra fuerza bruta. ``skip_captcha_login`` es
    la vía explícita para que el controller declare "esto no necesita
    captcha" (ver la sección de divergencias del docstring del módulo).
    """
    if skip_captcha_login is SKIP_CAPTCHA_LOGIN or skip_captcha_login is True:
        return False
    return credential.get('type') == 'password'


def apply_web_extensions():
    """Cuelga las extensiones de ``web`` sobre ``base.ResUsers``.

    Se invoca desde ``WebConfig.ready()`` (pendiente de sumar
    ``'addons.web.models.res_users'`` a ``WebConfig._EXTENSIONES`` — fase de
    consolidación del batch, ver ``apps.py``), mismo patrón que
    ``ir_http.py``/``res_partner.py``. ``name_search`` se asigna directo
    (no hay implementación previa que encadenar con ``chain_method``, y una
    reasignación del mismo valor es idempotente por construcción — a
    diferencia de ``chain_method``, no hace falta guardarla contra
    re-ejecuciones de ``ready()``).
    """
    chain_method(ResUsers, '_on_webclient_bootstrap', _on_webclient_bootstrap)
    chain_method(ResUsers, '_should_captcha_login', _should_captcha_login)
    ResUsers.name_search = classmethod(name_search)
