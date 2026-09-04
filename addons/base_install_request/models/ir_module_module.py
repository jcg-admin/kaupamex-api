"""``ir.module.module`` + la acción que abre la solicitud de activación.

Adaptación de ``odoo19c: addons/base_install_request/models/ir_module_module.py``
(LGPL-3, 19 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte completo — 1 de 1 símbolo
================================

La referencia declara **una** clase con **un** método::

    class IrModuleModule(models.Model):
        _inherit = 'ir.module.module'

        def action_open_install_request(self): ...

Aquí la clase destino es ``base.IrModule`` (el renombre está declarado en
``PORTE_ALIAS`` de ``scripts/check_porte_completo.py``, con su ``_name =
'ir.module.module'`` como prueba de que es la misma entidad), y el método se
cuelga con ``extend_model`` desde ``BaseInstallRequestConfig.ready()`` — el
idioma de este árbol para el ``_inherit`` cross-app.

``_inherit`` es el único atributo de clase que la fuente declara, y lo expresa
el destino de ``extend_model``: no hay ``_name``, ``_description`` ni ``_order``
que portar (medido con el recorrido AST de
``.claude/rules/atributos-de-clase-de-modelo.md`` sobre el archivo de la
referencia: ``IrModuleModule ['_inherit']``).

Por qué este método NO estaba bloqueado, y la marca que decía que sí
====================================================================

``models/base_module_install_request.py`` declaraba este addon **bloqueado en su
totalidad**, y ese veredicto era demasiado ancho: metía en el mismo saco la
ceremonia (pedir, revisar) y el acto central (instalar en caliente). Este método
no instala nada — devuelve un ``ir.actions.act_window``, que es el idioma que
**82 archivos** de este árbol ya usan (medido:
``grep -rln "ir.actions.act_window" --include=*.py addons/ src/ | wc -l``).

El bloqueo que **sí** se sostiene, medido y acotado a su símbolo, sigue
declarado en ``base_module_install_request.py``.

Divergencia declarada — el ``ensure_one()`` no se porta
========================================================

La fuente abre con ``self.ensure_one()`` porque allá ``self`` es un recordset y
el método necesita **un** registro. Aquí ``self`` es una instancia por
construcción, así que la guarda no tiene qué comprobar. Es el mismo criterio ya
escrito en ``src/addons/base/models/res_company.py:744`` y ``:821``.
"""
from orm.model_classes import extend_model
from tools.translate import _

#: El ``_name`` del asistente que la acción abre — la cadena verbatim de la
#: fuente. NO se resuelve contra un modelo de este árbol: el asistente está
#: bloqueado (ver ``base_module_install_request.py``), y la acción lo nombra
#: igual que la referencia. Mismo criterio que los xml_id sin resolver de
#: ``addons/crm/models/digest.py``.
INSTALL_REQUEST_MODEL = 'base.module.install.request'


def action_open_install_request(self):
    """Abre el formulario de solicitud de activación — ≙ ``:10-19``.

    Devuelve el ``ir.actions.act_window`` verbatim de la fuente: ventana nueva
    (``target: 'new'``), vista de formulario, el modelo del asistente, y el id
    de este módulo en el contexto como ``default_module_id``.

    El nombre lleva el ``shortdesc`` del módulo interpolado, como allá
    (``_('Activation Request of "%s"', self.shortdesc)``); aquí la
    interpolación va por ``kwargs`` nombrados, que es la firma de ``_`` en este
    árbol (``src/tools/translate.py:66``).
    """
    return {
        'type': 'ir.actions.act_window',
        'target': 'new',
        'name': _('Solicitud de activación de "%(module)s"',
                  module=self.shortdesc),
        'view_mode': 'form',
        'res_model': INSTALL_REQUEST_MODEL,
        'context': {'default_module_id': self.pk},
    }


def apply_base_install_request_extensions():
    """Cuelga la acción sobre ``base.IrModule``.

    La llama ``BaseInstallRequestConfig.ready()``: en tiempo de import del
    módulo el registro de modelos aún no está poblado.
    """
    extend_model('base', 'IrModule', metodos={
        'action_open_install_request': action_open_install_request,
    })
