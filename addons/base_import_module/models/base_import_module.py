"""``base.import.module`` — el asistente que sube el ``.zip`` de un módulo.

Adaptación de ``odoo19c: addons/base_import_module/models/base_import_module.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia preservados,
DEC-KX-03).

Porte BLOQUEADO — 9 de 11 símbolos
===================================

Nueve de este archivo (los dos atributos de clase, los seis campos y
``action_module_open``); dos bloqueados, cada uno con su medición y su
sucesor. El resto del addon —los cuatro archivos que extienden modelos
ajenos— se contabiliza en el docstring de ``models/__init__.py``.

Qué cambió respecto de la versión anterior de este docstring
=============================================================

Decía que el addon estaba vetado **en su totalidad** y no creaba ni el
modelo. Ese veredicto
mezclaba en un saco el **acto central** —instalar un addon en caliente, que
efectivamente no existe en esta plataforma— con **la ceremonia que lo rodea**,
que no depende de él: seis campos de formulario y una acción que abre una
lista. Es la misma forma de veredicto demasiado ancho que :ref:`h-api-1018`
registró para ``base_install_request``, y se corrige igual: el bloqueo pasa de
«el addon entero» a **una arista por símbolo**.

El bloqueo real, medido
========================

.. code-block:: text

   grep -rnE "def _import_zipfile|def _get_missing_dependencies_modules" \
       --include=*.py src/ addons/ | grep -v base_import_module | wc -l
   → 0

Instalar un addon contra una base viva es aquí una operación de **deploy**
(``INSTALLED_APPS`` + migración), y el veredicto no se inventa en este pase:
lo declara ``src/addons/base/models/ir_module.py`` — *"Las transiciones de
Odoo (to install / to upgrade / to remove) no se portan: son la máquina de
estados de un instalador que aquí no existe... Registrar un estado que nadie
puede alcanzar sería inventar una capacidad."*

Símbolo a símbolo
==================

- ``_name`` / ``_description`` (``:9-10``) — portados verbatim.
- ``module_file``, ``state``, ``import_message``, ``force``, ``with_demo``,
  ``modules_dependencies`` (``:12-17``) — los seis campos, portados.
- ``action_module_open`` (``:36-45``) — portado: devuelve un
  ``ir.actions.act_window``, el idioma que este árbol ya usa.
- ``import_module`` (``:19-30``) —
  BLOQUEADO por ``ir.module.module._import_zipfile`` — el método no existe en
  este árbol (medido arriba: 0 definiciones fuera de este addon). Sucesor:
  tarea **#452**, que porta lo que le falta a
  ``src/addons/base/models/ir_module.py``.
- ``get_dependencies_to_install_names`` (``:32-34``) —
  BLOQUEADO por ``ir.module.module._get_missing_dependencies_modules`` —
  misma medición, 0 definiciones. Sucesor: tarea **#452**.

Divergencias declaradas — de mecanismo, no de alcance
======================================================

- **``module_file`` es un ``BinaryField``, no un adjunto.** La fuente lo
  declara ``attachment=False`` justo para que el ``.zip`` viaje en la columna
  y no por ``ir.attachment``; aquí eso es un ``fields.Binary`` sin más, y el
  ``base64.decodebytes`` de la fuente no hace falta porque el valor ya llega
  en bytes.
- **``ensure_one()`` no se porta** — aquí ``self`` es una instancia por
  construcción; mismo criterio que ``src/addons/base/models/res_company.py:744``.

Lo que este archivo no cierra
==============================

Los dos símbolos bloqueados de arriba, ambos con sucesor declarado.
"""
import fields
import models

from orm.models_transient import TransientModel

#: ≙ ``state = fields.Selection([('init', 'init'), ('done', 'done')], …)``
#: (``odoo19c: :13``), con sus dos valores verbatim.
STATE_CHOICES = [('init', 'init'), ('done', 'done')]

#: El modelo que ``action_module_open`` abre — la cadena de la fuente (``:42``).
IR_MODULE_MODEL = 'ir.module.module'


class BaseImportModule(TransientModel):
    """≙ ``BaseImportModule`` (``odoo19c: :8-45``).

    Docstring de la fuente, verbatim: *"Import Module"*.
    """

    _name = 'base.import.module'
    _description = 'Import Module'

    module_file = fields.Binary(
        verbose_name='Module .ZIP file',
        help_text='El .zip del módulo (Odoo module_file, attachment=False).')
    state = fields.Selection(
        max_length=8, choices=STATE_CHOICES, default='init',
        verbose_name='Status',
        help_text='Odoo state: init mientras no se haya importado.')
    import_message = fields.Text(blank=True, default='')
    force = fields.Boolean(
        default=False, verbose_name='Force init',
        help_text='Force init mode even if installed. '
                  "(will update `noupdate='1'` records)")
    with_demo = fields.Boolean(
        default=False, verbose_name='Import demo data of module')
    modules_dependencies = fields.Text(blank=True, default='')

    class Meta:
        db_table = 'base_import_module'
        verbose_name = 'Importación de módulo'
        verbose_name_plural = 'Importaciones de módulo'

    def __str__(self):
        """La fuente no declara ``_rec_name``: el estado es lo que distingue."""
        return self.state

    def import_module(self):
        """BLOQUEADO por ``ir.module.module._import_zipfile`` — razón: el
        método no existe en este árbol (medido en el encabezado del módulo: 0
        definiciones fuera de este addon), porque instalar contra una base viva
        es aquí una operación de deploy. Sucesor: tarea **#452**.
        """
        raise NotImplementedError(
            'import_module está bloqueado: ir.module.module._import_zipfile no '
            'existe en este árbol (tarea #452).')

    def get_dependencies_to_install_names(self):
        """BLOQUEADO por ``ir.module.module._get_missing_dependencies_modules``
        — razón: el método no existe en este árbol (misma medición, 0
        definiciones fuera de este addon). Sucesor: tarea **#452**.
        """
        raise NotImplementedError(
            'get_dependencies_to_install_names está bloqueado: '
            'ir.module.module._get_missing_dependencies_modules no existe en '
            'este árbol (tarea #452).')

    def action_module_open(self, module_name=None):
        """≙ ``action_module_open`` (``odoo19c: :36-45``) — abre la lista.

        Devuelve el ``ir.actions.act_window`` verbatim de la fuente, con su
        dominio acotado a los módulos que el contexto nombra. La fuente lee
        ``self.env.context.get('module_name', [])``; aquí el dato llega por
        parámetro —el mismo criterio con que
        ``base_automation.get_webhook_request_payload`` recibe su ``request``—
        y sin él el dominio queda vacío, como allá cuando el contexto no trae
        la clave.
        """
        return {
            'domain': [('name', 'in', list(module_name or []))],
            'name': 'Modules',
            'view_mode': 'list,form',
            'res_model': IR_MODULE_MODEL,
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
