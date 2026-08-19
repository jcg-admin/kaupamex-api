r"""``res.groups`` extendido por ``account`` — dos métodos, uno bloqueado, uno adaptado.

Adaptación de ``addons/account/models/res_users.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 38 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Nota de nombre — igual que en la referencia
==============================================

El archivo se llama ``res_users.py`` en la fuente y aquí, pero el modelo que
extiende es ``res.groups``, no ``res.users`` — así lo declara la propia
referencia (``_inherit = 'res.groups'``, clase ``ResGroups``). Se conserva el
nombre de archivo tal cual la referencia lo tiene, por la misma regla de
SITIO que ``atributos-de-clase-de-modelo.md`` fija para el archivo, no para
la clase.

Porte símbolo por símbolo — 2 de 2, con desenlaces distintos
================================================================

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Símbolo
     - Estado
     - Nota
   * - ``get_application_groups``
     - **bloqueado**
     - el método base que sobreescribe no existe ni en nuestro árbol ni en
       la referencia Community disponible
   * - ``_activate_group_account_secured``
     - **adaptado**
     - ``_apply_group`` no existe aquí; se reexpresa con ``implied_ids``,
       el mecanismo que sí existe y hace lo mismo

``get_application_groups`` — bloqueado en DOS niveles
=========================================================

1. **En este árbol**: ``ResGroups`` (``src/addons/base/models/res_groups.py``)
   no declara ``get_application_groups`` — medido:
   ``grep -n "def get_application_groups" src/addons/base/models/res_groups.py``
   → 0 hits.
2. **En la propia referencia Community**: el método base al que la
   referencia le hace ``super().get_application_groups(domain)`` **tampoco
   está** en el árbol de Odoo disponible — medido:
   ``grep -rn "def get_application_groups" odoo-tools/…/odoo/`` → 0 hits en
   todo ``odoo/`` (sólo aparece la propia sobreescritura de ``account``, en
   ``addons/account/models/res_users.py``). [PROVEN, ambas mediciones]

Sin base que extender de ningún lado, portar esto sería inventar tanto el
método como su contrato. **Desenlace: DESCONOCIDO con condición de cierre** —
se retoma cuando exista, en cualquiera de los dos árboles, la definición del
método que se sobreescribe.

``_activate_group_account_secured`` — adaptado con ``implied_ids``
========================================================================

La referencia llama a ``group._apply_group(group_account_secured)`` por cada
grupo con acceso. ``_apply_group`` (``odoo/addons/base/models/
res_groups.py:308``) hace exactamente esto: añade el grupo implicado a
``self.implied_ids`` si aún no está — «Add the given group to the groups
implied by the current group». ``implied_ids`` **sí existe** en
``ResGroups`` de este árbol (``res_groups.py``, M2M reflexivo
``symmetrical=False``), así que el efecto se reexpresa directamente con esa
API pública, sin necesitar ``_apply_group`` en sí.

Divergencia declarada — ``env.ref`` por ``IrModelData``
============================================================

La referencia resuelve los tres/cuatro grupos por identificador externo
(``self.env.ref('account.group_account_secured', raise_if_not_found=False)``).
Este ORM no tiene un resolutor de XML ID genérico sobre cualquier modelo —
el patrón establecido en este árbol (``res_company.py``,
``load_chart_for_new_company``) es consultar ``ir.model.data`` directamente
por ``module``/``name``. Se porta con ese mismo patrón.

Medido: ninguno de los cinco grupos de seguridad de contabilidad
(``group_account_user``, ``group_account_readonly``, ``group_account_basic``,
``group_account_invoice``, ``group_account_secured``) está sembrado en este
árbol — ``grep -rln "group_account_secured" src/addons/base/data/*.py
addons/*/data/*.py`` → 0 hits [PROVEN]. El método queda **funcionalmente
inerte** hasta que exista esa siembra (fuera de alcance de este archivo: es
dato, no código); se porta igual porque su lógica es correcta y
autocontenida — un ``ir.model.data`` ausente resuelve a ``None`` y el método
no hace nada, sin lanzar.
"""
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups

#: Los cinco identificadores externos que la referencia consulta —
#: ``odoo19c: account/models/res_users.py``. Todos con ``module='account'``.
_GROUP_ACCOUNT_SECURED = 'group_account_secured'
_GROUPS_WITH_ACCESS = ('group_account_readonly', 'group_account_invoice')


def _group_by_xmlid(name, module='account'):
    """Resuelve un grupo por su identificador externo — ≙ ``self.env.ref``
    de la referencia, vía ``ir.model.data`` (el patrón ya establecido en
    ``res_company.py``). ``None`` si no está sembrado.
    """
    record = IrModelData.objects.filter(module=module, name=name).first()
    if record is None:
        return None
    return ResGroups.objects.filter(pk=record.res_id).first()


def _activate_group_account_secured(self):
    """≙ ``_activate_group_account_secured``
    (``odoo19c: account/models/res_users.py:30-38``).

    Añade ``group_account_secured`` a los ``implied_ids`` de los grupos con
    acceso (readonly + invoice), en vez de ``_apply_group`` (ausente aquí —
    ver el docstring del módulo). Sin efecto si alguno de los grupos no está
    sembrado (medido: ninguno lo está hoy).
    """
    secured = _group_by_xmlid(_GROUP_ACCOUNT_SECURED)
    if secured is None:
        return
    for name in _GROUPS_WITH_ACCESS:
        group = _group_by_xmlid(name)
        if group is not None:
            group.implied_ids.add(secured)


def apply_account_extensions():
    """≙ ``_inherit = 'res.groups'`` de ``account``.

    Sólo cuelga ``_activate_group_account_secured``: ``get_application_groups``
    queda DESCONOCIDO (ver docstring del módulo) — no se agrega un stub que
    finja una base inexistente.
    """
    if not hasattr(ResGroups, '_activate_group_account_secured'):
        ResGroups._activate_group_account_secured = _activate_group_account_secured
