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
``account`` lo site en el catalogo de reportes.

**Por que ``_get_report_values`` esta BLOQUEADO, y no es una excusa.** Su
unica linea sustantiva es ``self.env.company._check_hash_integrity()`` --
el metodo que recorre la cadena de hashes de los asientos contables
(anti-fraude) y devuelve el veredicto por diario
(``odoo19c: addons/account/models/company.py:1004``).

El bloqueo no es que ese metodo falte por si solo: es que falta la **cadena
de hash de inalterabilidad** entera de la que cuelga. Medido 2026-08-31
contra ``odoo19c: addons/account/models/account_move.py``, **7 de 7**
simbolos ausentes aqui -- ``_get_integrity_hash_fields``,
``_get_integrity_hash_fields_and_subfields``, ``_hash_moves``,
``_get_chain_info``, ``_calculate_hashes``, ``_compute_secured`` y
``_search_secured`` --, mas los campos ``account.move.inalterable_hash``,
``account.move.secure_sequence_number`` y
``account.journal.restrict_mode_hash_table`` (**0** en nuestro
``account_journal.py``), y la constante ``MAX_HASH_VERSION``.

La cita que el gate de ceros caducados vigila es la del simbolo clave de la
cadena: ``grep -c "def _calculate_hashes" addons/account/models/account_move.py``
da **0**. El dia que ese porte aterrice, el gate marca esta prosa como
caducada y obliga a reabrir el bloqueo -- que es exactamente lo que se
quiere, y lo que un sucesor citado solo por ordinal no consigue.

No se reimplementa el chequeo aqui: escribir la cadena sin medirla contra la
fuente corromperia la superficie anti-fraude con un veredicto no verificado.
Es el desenlace 2 de ``porte-completo-no-parcial.md`` --bloqueo medido con
sucesor registrado--, no una divergencia de mecanismo declarada.

Sucesor: tarea **#262**, que porta la cadena entera y con ella
``_check_hash_integrity`` en ``addons/account/models/res_company.py``. La
misma ausencia bloquea a otros cinco sitios: los cuatro asistentes de
``addons/account/wizard/`` y ``models/account_journal_dashboard.py``.

*Metrica:* ``def <simbolo>`` en el archivo de la referencia frente al
nuestro, y ``grep -rn`` de cada campo sobre ``addons/`` y ``src/``.
*Ciega a:* un porte de la cadena que renombre sus simbolos -- la comparacion
es por nombre literal, asi que un equivalente con otro nombre saldria como
ausente.

> **Corregido 2026-08-31 (:ref:`h-api-994`).** Este bloque citaba
> ``tarea #510`` como sucesor y ``#398`` como el alcance que lo excluia.
> Ninguno de los dos resuelve: el tablero de esta sesion llega a #261, y los
> ids de tarea **reinician por sesion** (tarea #3). Un bloqueo cuyo sucesor
> se cita por un ordinal que ya no resuelve queda sin sucesor que nadie
> pueda seguir -- que es justo lo que
> ``hallazgo-abierto-genera-sucesor.md`` existe para impedir, sólo que con
> la forma del cumplimiento puesta. El cero medido **si** se sostiene; lo
> que caduco fue el sucesor, no la premisa.

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
            ``ResCompany._check_hash_integrity`` exista (tarea #262).
        """
        if not isinstance(company, ResCompany):
            raise TypeError(
                f'company debe ser una instancia de ResCompany, no {type(company)!r}')
        if not hasattr(company, '_check_hash_integrity'):
            raise NotImplementedError(
                'ResCompany._check_hash_integrity no esta portado: falta la '
                'cadena de hash de inalterabilidad de account.move (7 de 7 '
                'simbolos ausentes, medido). Ver hallazgos H-API-682 y '
                'H-API-994, sucesor: tarea #262.'
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
