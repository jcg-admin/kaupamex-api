"""``account.update.tax.tags.wizard`` — el asistente "Actualizar casillas fiscales".

Adaptación de ``odoo19c: addons/account_update_tax_tags/wizard/
account_update_tax_tags_wizard.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``,
LGPL-3 — atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla
==========================================================

Mismo criterio que ``account_debit_note.AccountDebitNoteWizard`` (ver su
docstring): la referencia es ``models.TransientModel`` — "formulario, no
tabla". El estado del wizard (qué empresa, desde qué fecha) lo pasa el
llamador como parámetros de los classmethods, no una fila guardada.

Siete símbolos de la referencia — los siete se portan
=========================================================

===============================  ==========================================
Símbolo de la referencia          Qué pasa aquí
===============================  ==========================================
``company_id`` (campo)            PORTADO — parámetro ``company``
``date_from`` (campo)             PORTADO — parámetro ``date_from`` +
                                   ``compute_date_from(company)``
``display_lock_date_warning``     PORTADO — ``display_lock_date_warning
(campo)                           (company, date_from)``
``_compute_date_from``            PORTADO — ``compute_date_from()``
``_compute_display_lock_date_``   PORTADO — ``display_lock_date_warning()``
``warning``
``_modify_tag_to_aml_relation``   PORTADO — ``_modify_tag_to_aml_relation()``
``update_amls_tax_tags``          PORTADO — ``update_amls_tax_tags()``
===============================  ==========================================

Ningún símbolo se omite.

El prerrequisito bloqueado, y cómo se resolvió (no se difirió)
====================================================================

``_modify_tag_to_aml_relation`` de la referencia es una única consulta cruda
de PostgreSQL que asume tres columnas de ``account.move.line`` que este
árbol no porta (``tax_ids``, ``tax_repartition_line_id``, ``tax_tag_ids`` —
medido, ver ``models/account_move_line_tax_link.py``). Con el límite de esta
tarea ("no tocar ningún otro addon"), la resolución sancionada por
``porte-completo-no-parcial.md`` no es "declarar bloqueado y diferir": es
construir el mecanismo faltante DENTRO del alcance permitido. Los tres
modelos puente de ``models/`` cumplen ese papel; este archivo reimplementa
el ALGORITMO de la consulta cruda (los mismos cuatro pasos, mismas ramas de
``document_type``) contra esas tablas propias, vía ORM en vez de SQL crudo
de cuatro CTE encadenados — divergencia de TÉCNICA, no de resultado: el
conjunto de apuntes impactados y las casillas que terminan llevando es el
mismo que produciría la consulta de la referencia sobre un esquema que sí
tuviera esas tres columnas.

Los cuatro pasos de la referencia, y dónde quedan aquí
===========================================================

1. **Líneas base** (``base_aml_id_rep_tag_to_insert``) — para cada
   ``(apunte, impuesto aplicado)`` de ``AccountMoveLineTax``: si el impuesto
   es de grupo, se expande a sus hijos (``_expand_children``, ≙ el
   ``LEFT JOIN account_tax_filiation_rel`` + ``COALESCE``); se resuelve el
   ``document_type`` (factura/nota, ≙ el ``CASE`` gigante de la referencia,
   ver abajo); se busca la línea de reparto ``repartition_type='base'`` de
   ese impuesto y ``document_type`` (≙ el ``JOIN`` — si no hay, el par NO
   entra al resultado, igual que el ``INNER JOIN`` de la referencia
   descarta la fila); sus casillas entran al resultado (≙ el
   ``LEFT JOIN`` sobre ``rep_tags`` — sin casillas, entra con ``tag=None``).
2. **Líneas de impuesto** (``tax_aml_id_rep_tag_to_insert``) — para cada
   ``AccountMoveLineTaxRepartition`` del rango: sus casillas entran al
   resultado (mismo ``LEFT JOIN``, sin condición de ``document_type`` —
   la línea de reparto ya la fija).
3. **Unión + filtro por empresa/fecha** — ambos conjuntos se combinan en un
   solo ``set`` de pares ``(aml_id, tag_id)`` (≙ ``UNION``); el filtro
   ``company_id``/``date_from`` va en los ``.filter()`` de cada paso. Filtra
   por ``line__move__date`` (no ``line__date``): ``account.move.line`` de
   este árbol no porta ``date`` (Odoo la declara ``related='move_id.date',
   store=True``; aquí no hay related fields — se navega el FK directo).
4. **Borrar + insertar** — ``AccountMoveLineTag.objects.filter(line_id__in=
   candidate_ids).delete()`` seguido de ``bulk_create`` de los pares con
   ``tag_id`` no nulo (≙ ``DELETE`` + ``INSERT ... WHERE tag_id NOTNULL``).
   Devuelve la UNIÓN de los ``aml_id`` que tuvieron una fila borrada y los
   que tuvieron una fila insertada — no todo ``candidate_ids`` (≙
   ``impacted_aml`` de la referencia, que es
   ``delete_statement RETURNING ... UNION insert_statement RETURNING ...``:
   un apunte cuyo único par calculado es ``(aml, NULL)`` y que no tenía fila
   previa que borrar NO cuenta como impactado, aunque sí se evaluó).

``document_type`` para líneas base — el ``CASE`` de la referencia
=======================================================================

``odoo19c: :73-115`` (mismo archivo/commit). Tres ramas, en el mismo orden:

- ``move_type`` de factura/recibo (``in_invoice``, ``out_invoice``,
  ``in_receipt``, ``out_receipt``) → ``'invoice'``.
- ``move_type`` de nota de crédito (``in_refund``, ``out_refund``) →
  ``'refund'``.
- ``move_type == 'entry'`` → depende del signo del saldo y de
  ``type_tax_use`` del impuesto APLICADO (el padre, no el hijo expandido —
  ``COALESCE(parent_tax.type_tax_use, tax.type_tax_use)``, y como el campo
  no es nulo en este puerto, siempre resuelve al del padre): venta +
  saldo≤0 → factura; venta + saldo>0 → nota; compra + saldo≥0 → factura;
  compra + saldo<0 → nota. Ningún otro ``type_tax_use`` (``'none'``)
  resuelve — el par se descarta, igual que el ``INNER JOIN`` de la
  referencia cuando ninguna rama del ``CASE`` es verdadera.

Divergencias declaradas (con su medición)
==============================================

1. **CABA (cash basis) no se porta.** La referencia hace
   ``COALESCE(caba_origin_move.move_type, move.move_type)`` para que un
   asiento de base imponible en efectivo herede el ``document_type`` de la
   factura que lo originó. Medido: ``account.AccountMove`` de este árbol no
   tiene ``tax_cash_basis_origin_move_id`` (``grep -n
   "tax_cash_basis_origin_move_id" src/addons/account/models/account_move.py``
   → 0 hits) y ``account_tax_repartition_line.py`` ya declara
   ``tax_exigibility`` como no portado en ``AccountTax``. Sin la premisa
   (CABA), la rama no tiene entrada — se usa ``move.move_type`` siempre.
   Los dos tests de CABA de la referencia
   (``test_update_with_caba_taxes``, ``test_update_caba_taxes_with_
   negative_line``) NO se portan por esta razón, no por recorte de tiempo.
2. **Búsqueda de línea de reparto — ``.first()``, no todas.** La referencia
   arma el conjunto vía SQL sin ambigüedad porque cada combinación
   ``(tax, document_type, repartition_type='base')`` tiene una única fila en
   el modelo de datos de Odoo (una base por documento). Aquí se replica esa
   invariante con ``.first()`` en vez de iterar todas las que matcheen —
   mismo resultado bajo el mismo supuesto de datos (una base por
   documento), divergencia de forma de consulta, no de dato.
3. **Empresa como parámetro, no ``self.env.company``.** Igual que
   ``account_debit_note`` y el resto de wizards de este árbol: no hay
   contexto de request en el ORM (ver ``res_company.py``); la empresa la
   pasa el llamador.
"""
from datetime import date, timedelta

from addons.account.models.account_tax import AccountTax
from addons.account.models.account_tax_repartition_line import AccountTaxRepartitionLine
from addons.account_update_tax_tags.models.account_move_line_tax_link import (
    AccountMoveLineTag,
    AccountMoveLineTax,
    AccountMoveLineTaxRepartition,
)
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


class AccountUpdateTaxTagsWizard(TransientModel):
    """Asistente "Actualizar casillas fiscales" — ≙
    ``account.update.tax.tags.wizard``.

    Sin tabla (``TransientModel``, ``managed = False``): el estado del
    wizard lo pasa el llamador como argumentos de los classmethods.
    """

    class Meta:
        abstract = True
        managed = False

    #: ≙ el primer bloque del ``CASE`` de ``_modify_tag_to_aml_relation``
    #: (``odoo19c: :75-79``): estos ``move_type`` resuelven a ``'invoice'``.
    INVOICE_MOVE_TYPES = ('out_invoice', 'in_invoice', 'out_receipt', 'in_receipt')
    #: ≙ el segundo bloque (``:81-85``): estos resuelven a ``'refund'``.
    REFUND_MOVE_TYPES = ('out_refund', 'in_refund')

    # ==== Compute methods (≙ los dos @api.depends de la referencia) ====
    @classmethod
    def compute_date_from(cls, company):
        """≙ ``_compute_date_from`` (``odoo19c: :22-26``).

        Un día después del candado fiscal, o hoy si no hay candado fijado.
        """
        tax_lock_date = company.tax_lock_date
        return tax_lock_date + timedelta(days=1) if tax_lock_date else date.today()

    @classmethod
    def display_lock_date_warning(cls, company, date_from):
        """≙ ``_compute_display_lock_date_warning`` (``odoo19c: :28-32``)."""
        tax_lock_date = company.tax_lock_date
        return bool(tax_lock_date and date_from < tax_lock_date)

    # ==== Business methods (≙ los dos métodos de negocio) ====
    @classmethod
    def _expand_children(cls, tax):
        """Un impuesto de grupo se expande a sus hijos; si no, es él mismo.

        ≙ ``LEFT JOIN account_tax_filiation_rel ... COALESCE(child_tax,
        tax_id)`` (``odoo19c: :61-67``). ``AccountTax.children`` (este
        árbol, ``db_table='account_tax_filiation_rel'``) es el mismo M2M
        que la referencia declara como ``children_tax_ids``.
        """
        children = list(tax.children.all())
        return children if children else [tax]

    @classmethod
    def _document_type_for_base_line(cls, move, line, applied_tax):
        """≙ el ``CASE`` de ``document_type`` para líneas base (``:73-115``).

        Devuelve ``'invoice'``/``'refund'``, o ``None`` cuando ninguna rama
        aplica (impuesto ``type_tax_use='none'`` sobre un asiento libre) —
        el llamador descarta el par, igual que el ``INNER JOIN`` de la
        referencia.
        """
        move_type = move.move_type
        if move_type in cls.INVOICE_MOVE_TYPES:
            return 'invoice'
        if move_type in cls.REFUND_MOVE_TYPES:
            return 'refund'
        # move_type == 'entry': el signo del saldo decide, según el uso
        # del impuesto APLICADO (el padre — COALESCE(parent_tax..., ...)).
        type_tax_use = applied_tax.type_tax_use
        if type_tax_use == 'sale':
            return 'invoice' if line.balance <= 0 else 'refund'
        if type_tax_use == 'purchase':
            return 'invoice' if line.balance >= 0 else 'refund'
        return None

    @classmethod
    def _base_repartition_line_for(cls, tax, document_type):
        """La línea de reparto ``repartition_type='base'`` de ``tax`` para
        ``document_type`` — ≙ el ``JOIN account_tax_repartition_line`` de la
        referencia (ver divergencia declarada #2 del docstring del módulo)."""
        return AccountTaxRepartitionLine.objects.filter(
            tax=tax, repartition_type='base', document_type=document_type,
        ).first()

    @classmethod
    def _base_line_tag_pairs(cls, company, date_from):
        """Pares ``(aml_id, tag_id)`` de líneas base — ≙
        ``base_aml_id_rep_tag_to_insert`` (``odoo19c: :51-119``)."""
        pairs = set()
        links = (
            AccountMoveLineTax.objects
            .filter(line__move__company=company, line__move__date__gte=date_from)
            .select_related('line', 'line__move', 'tax')
        )
        for link in links:
            line, applied_tax, move = link.line, link.tax, link.line.move
            for tax in cls._expand_children(applied_tax):
                document_type = cls._document_type_for_base_line(move, line, applied_tax)
                if document_type is None:
                    continue
                rep_line = cls._base_repartition_line_for(tax, document_type)
                if rep_line is None:
                    continue
                tags = list(rep_line.tag_ids.all())
                if not tags:
                    pairs.add((line.pk, None))
                else:
                    pairs.update((line.pk, tag.pk) for tag in tags)
        return pairs

    @classmethod
    def _tax_line_tag_pairs(cls, company, date_from):
        """Pares ``(aml_id, tag_id)`` de líneas de impuesto — ≙
        ``tax_aml_id_rep_tag_to_insert`` (``odoo19c: :121-129``)."""
        pairs = set()
        links = (
            AccountMoveLineTaxRepartition.objects
            .filter(line__move__company=company, line__move__date__gte=date_from)
            .select_related('line', 'repartition_line')
        )
        for link in links:
            tags = list(link.repartition_line.tag_ids.all())
            if not tags:
                pairs.add((link.line_id, None))
            else:
                pairs.update((link.line_id, tag.pk) for tag in tags)
        return pairs

    @classmethod
    def _modify_tag_to_aml_relation(cls, company, date_from):
        """Reescribe las casillas vigentes de los apuntes del rango — ≙
        ``_modify_tag_to_aml_relation`` (``odoo19c: :35-170``).

        Devuelve la UNIÓN de los ``id`` de apuntes que tuvieron una fila
        borrada y los que tuvieron una fila insertada — no todo
        ``candidate_ids`` (ver la nota del paso 4 en el docstring del
        módulo: un par ``(aml, None)`` sin fila previa que borrar no cuenta
        como impactado, aunque sí se evaluó).
        """
        pairs = cls._base_line_tag_pairs(company, date_from) | cls._tax_line_tag_pairs(company, date_from)
        candidate_ids = {aml_id for aml_id, _tag_id in pairs}
        if not candidate_ids:
            return []
        deleted_ids = set(
            AccountMoveLineTag.objects
            .filter(line_id__in=candidate_ids)
            .values_list('line_id', flat=True)
            .distinct()
        )
        AccountMoveLineTag.objects.filter(line_id__in=candidate_ids).delete()
        to_insert = [
            AccountMoveLineTag(line_id=aml_id, tag_id=tag_id)
            for aml_id, tag_id in pairs if tag_id is not None
        ]
        AccountMoveLineTag.objects.bulk_create(to_insert)
        inserted_ids = {row.line_id for row in to_insert}
        return sorted(deleted_ids | inserted_ids)

    @classmethod
    def update_amls_tax_tags(cls, company, date_from):
        """Punto de entrada del wizard — ≙ ``update_amls_tax_tags`` (``:172-183``).

        Valida que ningún impuesto hijo pertenezca a más de un padre entre
        los impuestos con hijos de ``company`` (≙ la comparación de
        longitudes de la referencia: ``len(children_taxes) >
        len(parent_taxes.children_tax_ids.ids)`` — aquí expresada
        directamente como "algún hijo aparece duplicado en la lista de
        aristas padre→hijo", el mismo invariante sin depender de la
        semántica de unión de un recordset Odoo), y reescribe las casillas.
        """
        parent_taxes = AccountTax.objects.filter(company=company, children__isnull=False).distinct()
        child_ids = []
        for tax in parent_taxes:
            child_ids.extend(tax.children.values_list('pk', flat=True))
        if len(child_ids) > len(set(child_ids)):
            raise UserError(_(
                'No se puede actualizar con impuestos hijos que pertenezcan '
                'a múltiples padres.'))
        return cls._modify_tag_to_aml_relation(company, date_from)
