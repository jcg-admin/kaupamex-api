"""Lo que ``sale`` añade al parámetro de configuración — ≙ ``_inherit``.

Origen: ``odoo19c: sale/models/ir_config_parameter.py`` (LGPL-3 según su
``__manifest__.py``: copia + adaptación con atribución).

Cinco símbolos, y los cinco giran alrededor de una idea: **dos parámetros de
configuración son el interruptor de dos tareas periódicas**, y el interruptor
tiene que llegar a la tarea sin que nadie se acuerde de propagarlo. Por eso los
tres enganches de mutación —``create``, ``write``, ``unlink``— sincronizan el
``active`` de la tarea enlazada.

El orden de delegación **no es el mismo en los tres**, y ésa es la razón de que
este archivo use ``overrides=`` y no ``metodos=``:

===========  ==============================================================
``create``   ``super()`` primero; sincroniza sobre lo que devolvió (``:12-15``)
``write``    ``super()`` primero; sincroniza después (``:17-20``)
``unlink``   sincroniza **primero**, con ``unlink=True``; delega al final
             (``:22-24``) — la fila tiene que existir todavía para leer su
             clave
===========  ==============================================================

Un mecanismo que fije el orden no puede replicar los tres; por eso
:func:`~orm.method_chain.wrap_method` entrega la implementación previa en la
mano, que es lo que ``super()`` es.

Divergencia de mecanismo declarada (no símbolo omitido): el ``self.filtered``
de la fuente recorre un **recordset**, y aquí ``create`` recibe la lista de
instancias recién creadas mientras ``write``/``unlink`` operan sobre **una**.
:func:`_sale_sync_linked_crons` acepta las dos formas por eso.
"""
from addons.base.models.ir_model import IrModelData
from addons.sale import const
from orm.model_classes import extend_model
from tools.misc import str2bool


def create(cls, previous, vals_list, using=None):
    """≙ ``create`` (``odoo19c: :12-15``) — ``@api.model_create_multi``.

    Delega primero y sincroniza sobre lo creado, igual que la fuente. El
    ``using`` viaja tal cual: el ``create`` de ``SystemParameter`` lo declara y
    la sincronización tiene que leer la misma base.
    """
    configs = (previous(vals_list) if using is None
               else previous(vals_list, using=using))
    _sale_sync_linked_crons(configs)
    return configs


def write(self, previous, vals, using=None):
    """≙ ``write`` (``odoo19c: :17-20``).

    Delega primero —el valor nuevo tiene que estar escrito para que la tarea
    lo lea— y sincroniza después.
    """
    result = previous(vals) if using is None else previous(vals, using=using)
    _sale_sync_linked_crons(self)
    return result


def unlink(self, previous, using=None):
    """≙ ``unlink`` (``odoo19c: :22-24``).

    Sincroniza **antes** de delegar, con ``unlink=True``: después de borrar la
    fila ya no hay clave que consultar. Es el orden contrario al de sus dos
    hermanos, y es la razón por la que este archivo necesita el ``super()``
    explícito.
    """
    _sale_sync_linked_crons(self, unlink=True)
    return previous() if using is None else previous(using=using)


def _sale_sync_linked_crons(configs, unlink=False):
    """≙ ``_sale_sync_linked_crons`` (``odoo19c: :26-37``).

    Sincroniza el ``active`` de las tareas periódicas de ventas según el
    parámetro que las gobierna.

    :param configs: una instancia de ``ir.config_parameter`` o un iterable de
        ellas. La fuente recibe siempre un recordset y filtra con
        ``self.filtered``; aquí las dos formas llegan según el enganche que
        llame, y se normalizan.
    :param bool unlink: si la sincronización viene de un borrado. Entonces la
        tarea se apaga, sin consultar el valor.
    """
    mapping = _get_param_cron_mapping()
    for config in _as_iterable(configs):
        if config.key not in mapping:
            continue
        linked_cron = _resolve_cron(mapping[config.key])
        if linked_cron is None:
            # ≙ ``raise_if_not_found=False`` (``odoo19c: :35``): la tarea puede
            # no estar sembrada todavía, y eso no es un error del parámetro.
            continue
        linked_cron.active = False if unlink else str2bool(config.value)
        linked_cron.save(update_fields=['active'])


def _get_param_cron_mapping():
    """≙ ``_get_param_cron_mapping`` (``odoo19c: :39-45``).

    Devuelve el mapa parámetro → identificador externo de su tarea. Existe
    como método propio en la fuente para que un addon posterior lo amplíe; se
    conserva por eso, no porque el cuerpo lo necesite.
    """
    return const.PARAM_CRON_MAPPING


def _as_iterable(configs):
    """Un recordset o una instancia suelta, siempre como iterable.

    La fuente no lo necesita —``self`` siempre es un recordset— y aquí sí: el
    ``create`` portado devuelve una lista y ``write``/``unlink`` operan sobre
    una instancia. Es la divergencia de mecanismo declarada en la cabecera.
    """
    if configs is None:
        return ()
    return configs if isinstance(configs, (list, tuple, set)) else (configs,)


def _resolve_cron(xmlid):
    """La tarea periódica que nombra ``xmlid``, o ``None`` si no está sembrada.

    ≙ ``self.env.ref(linked_cron_xmlid, raise_if_not_found=False)``
    (``odoo19c: :35``). Este árbol no tiene el objeto ``env``, y su atajo vive
    en ``IrModelData.ref`` — que es el mismo cuerpo: resolver el identificador
    externo y traer el registro.
    """
    return IrModelData.ref(xmlid, raise_if_not_found=False)


def apply_sale_config_parameter_extensions():
    """Cuelga los cinco símbolos sobre ``ir.config_parameter``.

    La invoca ``SaleConfig.ready()``. Los tres enganches de mutación van por
    ``overrides=`` —necesitan el ``super()`` explícito—; los dos ayudantes son
    nuevos y van por ``metodos=``.
    """
    extend_model(
        'base', 'SystemParameter',
        metodos={
            '_sale_sync_linked_crons': staticmethod(_sale_sync_linked_crons),
            '_get_param_cron_mapping': staticmethod(_get_param_cron_mapping),
        },
        overrides={
            'create': classmethod(create),
            'write': write,
            'unlink': unlink,
        },
    )
