"""``base`` extendido por ``html_editor`` — dos atributos de campo para la vista.

Adaptación de ``odoo19c: addons/html_editor/models/models.py``
(14 líneas, LGPL-3 — copia + adaptación con atribución, DEC-KX-03).

**2 símbolos en la fuente, 2 portados, 0 ausentes.** La clase ``Base`` y su
método ``_get_view_field_attributes``.

Qué hace
========

``base`` es la raíz implícita de todo modelo, y publica la lista de atributos
de campo que una vista puede consultar. Este archivo le añade dos:
``sanitize`` y ``sanitize_tags``.

No es decoración: el editor pregunta por ellos para decidir **si un campo HTML
se puede editar y con qué libertad**. Sin publicarlos, el cliente no tiene
forma de distinguir un campo saneado de uno que no lo está, y trataría a los
dos igual.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``_inherit = 'base'``            ``chain_method`` sobre
                                 ``base.ir_model.Base`` — la clase que
                                 este árbol declara con ``_name =
                                 'base'`` para que las citas
                                 ``_inherit = 'base'`` tengan destino
``super()...append(...)``        **cpython** — el ``combine``
                                 ``extend_list`` de
                                 ``orm.method_chain``, que es el idioma
                                 de esta familia
===============================  =====================================

Divergencia declarada
=====================

``base.Base`` de este árbol **no declara** ``_get_view_field_attributes``, así
que ``chain_method`` lo instala tal cual y encadenará el día que alguien lo
declare debajo. El ``combine`` va puesto desde ya por la misma razón por la
que ``http_routing`` lo hace en ``ir_qweb.py``: el método es acumulativo por
contrato, y descubrirlo el día del segundo eslabón es descubrirlo tarde.

Los dos atributos que publica **todavía no existen** en
``orm.fields_textual.Html`` — su docstring declara que va *"sin saneo (capa
UI)"*. Es la misma divergencia que ``html_field_history_mixin.py`` declara con
más detalle, y comparten sucesor: dotar a ``fields.Html`` de
``sanitize``/``sanitize_tags``. Publicar los nombres **ahora** es correcto de
todos modos — el contrato de la vista es la lista de nombres, no su valor, y
quien los consulte hoy obtiene la ausencia del atributo, que es un dato cierto.
"""
from addons.base.models.ir_model import Base
from orm.method_chain import chain_method, extend_list


def _get_view_field_attributes(self):
    """≙ ``_get_view_field_attributes`` (``odoo19c: :7-11``).

    La fuente lo declara ``@api.model`` y hace ``keys = super()...`` seguido
    de dos ``append``. Aquí devuelve **sólo lo propio** y el ``combine``
    ``extend_list`` lo concatena detrás de lo previo, que es el mismo orden.
    """
    return ['sanitize', 'sanitize_tags']


def apply_html_editor_extensions():
    """Cuelga el método sobre ``base.Base`` — ≙ ``_inherit = 'base'``."""
    chain_method(Base, '_get_view_field_attributes',
                 _get_view_field_attributes, combine=extend_list)
