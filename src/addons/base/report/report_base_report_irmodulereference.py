"""``report.base.report_irmodulereference`` — referencia técnica de un módulo.

Adaptación de
``odoo19c: odoo/addons/base/report/report_base_report_irmodulereference.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia preservados,
DEC-KX-03).

Provee los valores del reporte que documenta qué modelos —y qué campos de cada
uno— aporta un módulo. En la referencia es un ``AbstractModel`` cuyos tres
métodos consume la plantilla QWeb; aquí es una clase con ``classmethod``, el
precedente "formulario, no tabla" ya fijado por ``base/wizard/``.

Cobertura del porte — 2 de 3 símbolos
======================================

.. list-table::
   :header-rows: 1

   * - Símbolo
     - Estado
   * - ``_object_find``
     - portado — ``IrModelData`` e ``IrModel`` existen
   * - ``_get_report_values``
     - portado — ``get_report_from_name`` e ``IrModule`` existen
   * - ``_fields_find``
     - **BLOQUEADO** en ``fields_get``; ver abajo

**Por qué ``_fields_find`` no se porta, y no es una excusa.** Su última línea
es ``self.env[model].fields_get(fnames)`` — el descriptor de los campos del
modelo. Medido en este árbol: ``def fields_get`` da **0** apariciones, y
portarlo arrastra otros dos mecanismos ausentes:

- ``field.get_description(env, attributes)`` — **0** apariciones en
  ``src/orm/``; habría que declararlo en las doce clases de campo.
- ``self._has_field_access(field, 'read')`` → ``env.user.has_groups(...)`` —
  ``def has_groups`` da **0** en ``res_users.py`` (es el mismo hueco que
  :ref:`h-api-619` registra desde otro llamador).

Los tres viven en ``odoo/orm/models.py`` y ``odoo/orm/fields.py``, no en
``addons/base``: su hogar es la tarea **#291** (medir ``src/orm`` contra
``odoo/orm``), no ésta. Sucesor registrado: tarea **#399**.

**El bloqueo es ruidoso, no vacío.** ``_fields_find`` levanta
``NotImplementedError`` con el motivo. Devolver ``[]`` —que es lo que la fuente
hace cuando no encuentra datos— produciría un reporte con la sección de campos
en blanco y sin nada que lo delate: exactamente el OK silencioso que
``check_silent_oks`` existe para impedir.

Lo que este archivo NO trae, y no es olvido
============================================

El ``ReportSpec`` del reporte. La referencia lo declara en
``ir_actions_report.xml`` —otro archivo, no éste— y aquí el equivalente vive en
el ``report/report_catalog.py`` del addon dueño, con un ``builder`` que dibuja
el PDF. Declararlo exige diseñar ese documento, que es trabajo de otra pieza;
es el mismo fenómeno que la tarea **#279** registra para ``stock``.
"""
from addons.base.models.ir_actions_report import IrActionsReport
from addons.base.models.ir_model import IrModel, IrModelData
from addons.base.models.ir_module import IrModule

#: ``report_name`` del reporte al que sirve (``odoo19c: :30``).
REPORT_NAME = 'base.report_irmodulereference'


class ReportBaseReportIrmodulereference:
    """≙ ``report.base.report_irmodulereference`` (``odoo19c: :7-9``)."""

    @classmethod
    def _object_find(cls, module):
        """≙ ``_object_find`` (``odoo19c: :11-16``): los modelos del módulo.

        La fuente busca en ``ir.model.data`` las filas que apuntan a
        ``ir.model`` y pertenecen al módulo, y devuelve esos ``ir.model``. El
        rodeo por el registro de datos —en vez de un campo directo— es
        deliberado allá: es lo que hace que un modelo "pertenezca" al módulo
        que lo declaró, y no al que lo extiende.

        El ``.sudo()`` de la fuente no se porta: aquí la elevación es un canal
        separado del dato (DEC-AISL-04), y un queryset del ORM no lo lleva.
        Quien necesite saltarse el row-scoping lo pide explícitamente.
        """
        res_ids = IrModelData.objects.filter(
            model='ir.model', module=module.name,
        ).values_list('res_id', flat=True)
        return IrModel.objects.filter(pk__in=list(res_ids))

    @classmethod
    def _fields_find(cls, model, module):
        """≙ ``_fields_find`` (``odoo19c: :18-26``) — **BLOQUEADO**.

        :raises NotImplementedError: siempre. El descriptor de campos
            (``fields_get``) no existe en este árbol, ni las dos piezas de las
            que depende. Ver la cobertura del porte en el docstring del módulo
            y la tarea **#399**.
        """
        raise NotImplementedError(
            'report.base.report_irmodulereference._fields_find requiere '
            'fields_get, que este arbol no declara (0 apariciones). Arrastra '
            'ademas Field.get_description y ResUsers.has_groups, tambien '
            'ausentes. Hogar del porte: tarea #291 (src/orm vs odoo/orm); '
            'sucesor: tarea #399.'
        )

    @classmethod
    def _get_report_values(cls, docids, data=None):
        """≙ ``_get_report_values`` (``odoo19c: :28-38``).

        Devuelve el contexto que consume la plantilla: los módulos
        seleccionados y los dos buscadores como callables, tal cual la fuente
        —que los pasa por nombre (``findobj`` / ``findfields``) para que la
        plantilla los invoque por módulo y por modelo.

        ``findfields`` viaja aunque esté bloqueado: la plantilla que lo invoque
        recibirá el ``NotImplementedError`` con su motivo, que es mejor
        diagnóstico que una clave ausente a mitad del render.
        """
        report = IrActionsReport._get_report_from_name(REPORT_NAME)
        selected_modules = IrModule.objects.filter(pk__in=list(docids))
        return {
            'doc_ids': docids,
            # ``report`` puede ser ``None``: el ``ReportSpec`` de este reporte
            # aún no se declara (ver el docstring del módulo). La fuente asume
            # que existe porque su XML lo siembra al instalar el addon.
            'doc_model': report.model if report else None,
            'docs': selected_modules,
            'findobj': cls._object_find,
            'findfields': cls._fields_find,
        }
