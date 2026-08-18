"""``report.account.report_hash_integrity`` -- resultado de integridad de
hash como PDF.

Adaptacion de ``odoo19c:
addons/account/report/account_hash_integrity_templates.py``
(``odoo-tools@622ddc2a``, LGPL-3 -- atribucion y aviso de licencia
preservados, DEC-KX-03).

Cobertura del porte -- 1 de 1 simbolo (con su unico metodo BLOQUEADO)
=======================================================================

.. list-table::
   :header-rows: 1

   * - Simbolo
     - Estado
   * - ``ReportAccountReport_Hash_Integrity._get_report_values``
     - BLOQUEADO -- ver abajo

**Divergencia de forma -- clase, no modelo.** La fuente es un
``models.AbstractModel`` porque el motor QWeb de Odoo resuelve el
``_get_report_values`` de un ``report_name`` via el registro de modelos.
Este arbol no tiene motor QWeb de reportes cableado para ``account`` (medido:
``grep -rln "report_catalog.py" addons/account/`` -> 0 hits; el precedente de
"formulario, no tabla" para este mismo patron ya esta fijado en
``src/addons/base/report/report_base_report_irmodulereference.py``, que
adapta un ``AbstractModel`` de solo-lectura a una clase con
``classmethod``). Se sigue ese mismo precedente aqui: la clase deja de ser
un modelo Django y pasa a ser un ensamblador de valores puro, invocable
desde el ``builder`` que el dia que exista el ``report_catalog.py`` de
``account`` (fuera de la lista de archivos escribibles de la tarea #398) lo
site en el catalogo de reportes.

**Por que ``_get_report_values`` esta BLOQUEADO, y no es una excusa.** Su
unica linea sustantiva es ``self.env.company._check_hash_integrity()`` --
el metodo que recorre la cadena de hashes de los asientos contables
(anti-fraude) y devuelve el veredicto por diario. Medido en este arbol:
``grep -rn "_check_hash_integrity" addons/ src/`` -> **0** apariciones. Es
un metodo de ``res.company`` que ``account`` le cuelga
(``odoo19c: addons/account/models/company.py``), es decir un simbolo de
``addons/account/models/**`` -- explicitamente fuera de mi alcance de
escritura en esta tarea. No se inventa el chequeo de integridad de hash aqui:
eso corrompería la superficie anti-fraude con una implementación no
verificada contra la referencia. Sucesor registrado: tarea **#510** (portar
``_check_hash_integrity`` en ``addons/account/models/res_company.py``,
tramo que cae fuera de esta tarea #398).

El bloqueo es ruidoso, no vacio: ``_get_report_values`` levanta
``NotImplementedError`` con el motivo, en vez de devolver un ``dict`` vacio
o silenciosamente incompleto -- exactamente el OK silencioso que
``check_silent_oks`` existe para impedir.
"""
from addons.base.models.res_company import ResCompany

#: ``report_name`` del reporte al que sirve (``odoo19c:
#: addons/account/report/account_hash_integrity_templates.py:9``).
REPORT_NAME = 'account.report_hash_integrity'


class ReportAccountReportHashIntegrity:
    """>= ``report.account.report_hash_integrity`` (``odoo19c:
    account_hash_integrity_templates.py:6-9``)."""

    @classmethod
    def _get_report_values(cls, company, docids, data=None):
        """>= ``_get_report_values`` (``odoo19c:
        account_hash_integrity_templates.py:11-19``).

        La fuente resuelve la empresa via ``self.env.company``; aqui se
        recibe explicita (mismo criterio que
        ``ResDevice.is_current(self, request)`` en
        ``src/addons/base/models/res_device.py`` -- "formulario, no
        tabla" pasa el contexto por parametro en vez de un global
        implicito).

        :param company: la instancia de ``ResCompany`` cuya cadena de
            hashes se verifica.
        :param docids: ids del documento solicitado (pasan intactos al
            resultado, fieles a la fuente).
        :param data: datos adicionales del reporte; si trae claves, se
            fusionan con el resultado de la verificacion (misma prioridad
            que la fuente: ``data.update(...)``, el chequeo puede
            sobrescribir claves de ``data``).
        :raises NotImplementedError: siempre, hasta que
            ``ResCompany._check_hash_integrity`` exista (tarea #510).
        """
        if not isinstance(company, ResCompany):
            raise TypeError(
                f'company debe ser una instancia de ResCompany, no {type(company)!r}')
        if not hasattr(company, '_check_hash_integrity'):
            raise NotImplementedError(
                'ResCompany._check_hash_integrity no esta portado '
                '(addons/account/models/res_company.py, fuera de mi alcance '
                'de escritura en la tarea #398). Ver hallazgo H-API-682, '
                'sucesor: tarea #510.'
            )
        integrity_result = company._check_hash_integrity()  # noqa: SLF001
        if data:
            data = {**data, **integrity_result}
        else:
            data = integrity_result
        return {
            'doc_ids': docids,
            'doc_model': ResCompany,
            'data': data,
            'docs': ResCompany.objects.filter(pk=company.pk),
        }
