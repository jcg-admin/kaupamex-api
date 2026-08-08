r"""Puente hacia ``account.move.line`` — prerrequisito NO portado del wizard.

Adaptación de ``odoo19c: addons/account_update_tax_tags/wizard/
account_update_tax_tags_wizard.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``,
LGPL-3 — atribución y aviso de licencia preservados, DEC-KX-03).

Qué mide este archivo, y qué NO puede ver
==============================================

La consulta cruda de la referencia (``_modify_tag_to_aml_relation``) da por
sentados tres campos de ``account.move.line`` (Odoo 19,
``account_move_line.py:194-230``, mismo commit)::

    tax_ids                  = fields.Many2many('account.tax', ...)
    tax_repartition_line_id  = fields.Many2one('account.tax.repartition.line', ...)
    tax_tag_ids               = fields.Many2many('account.account.tag', ...)

Medido en este árbol: **ninguno de los tres existe.**
``api: src/addons/account/models/account_move_line.py`` porta sólo los
campos núcleo (``move``, ``account``, ``name``, ``debit``, ``credit``,
``balance``, ``display_type``, ``quantity``, ``price_unit``, ``currency``,
``full_reconcile``, ``matching_number`` — ver su docstring). El propio
``account_tax_repartition_line.py`` de este árbol ya declara la ausencia como
premisa de su propia existencia: *"Es el prerrequisito de
``account_update_tax_tags`` (bloqueado hasta este port)"*. Y
``account_tax.py`` documenta que la **envoltura** de base-lines hacia la
contabilidad —lo que persistiría estos tres campos al postear una factura—
está deliberadamente fuera de alcance ("Qué no se porta" en ese archivo):
motor de cómputo portado, envoltura no.

Métrica: ``grep -rn "tax_tag_ids\|tax_line_id\|tax_repartition_line_id"
src/addons/account/models/*.py`` → 0 hits (medido antes de escribir este
archivo). Ciega a: si esos campos existieran con otro nombre — no es el
caso, el grep de ``tax_ids\b`` (excluyendo ``original_tax_ids``/
``replacing_tax_ids``/``children_tax_ids``) también da 0 en ``account/``.

Por qué NO se resuelve con ``add_to_class`` (precedente ``account_fleet``)
================================================================================

El patrón establecido en este árbol para que un addon satélite añada un
campo a un modelo ajeno es ``add_to_class`` desde ``AppConfig.ready()``
(``api: src/addons/account_fleet/models/account_move.py``, campo
``vehicle`` sobre ``AccountMoveLine``). Ese patrón **funciona**, pero su
migración resultante vive físicamente en el directorio de migraciones del
app QUE POSEE el modelo — medido:
``api: src/addons/account/migrations/0017_accountmoveline_vehicle.py``
(``model_name="accountmoveline"``, generada bajo ``account/``, no bajo
``account_fleet/``). Django ata el ``app_label`` de una operación de
migración al app del propio archivo de migración: no hay forma de que una
migración en ``account_update_tax_tags/migrations/`` altere el estado de
``accountmoveline`` sin que ese estado ya pertenezca a este app.

Esta tarea tiene un límite explícito y más estrecho que el precedente:
*"Escribe SÓLO dentro de .../account_update_tax_tags/ ... No toques ningún
otro addon."* Aplicar ``add_to_class`` con fidelidad total exigiría escribir
``account/migrations/0018_*.py`` — fuera de ese límite. La resolución
sancionada por ``porte-completo-no-parcial.md`` ("si el stack no trae el
mecanismo, se construye") se aplica aquí construyendo el vínculo como
modelos PROPIOS de este addon — mismo criterio que ``DEC-SALE-01`` ya usa
para ``account_debit_note.AccountMoveDebitNote`` (dato nuevo sobre
``account.move`` sin tocar ``account``): FK/M2M desde una tabla nueva hacia
el modelo ajeno, sin escribir ni una línea en ``account/``.

Los tres puentes, uno por campo ausente
==========================================

===============================  ======================================================
Campo Odoo ausente                 Puente en este addon
===============================  ======================================================
``tax_ids`` (M2M, base line)       ``AccountMoveLineTax`` (línea, impuesto)
``tax_repartition_line_id`` (M2O)  ``AccountMoveLineTaxRepartition`` (línea única, reparto)
``tax_tag_ids`` (M2M, destino)     ``AccountMoveLineTag`` (línea, casilla) — la que
                                    ``AccountUpdateTaxTagsWizard`` reescribe
===============================  ======================================================

Ningún símbolo se omite: los tres son prerrequisitos de datos, no de
comportamiento — no hay método de la referencia que quede sin destino.

Divergencia de mecanismo declarada, no recorte
==================================================

Estas tres tablas **no existen en la referencia** — Odoo las declara como
columnas/M2M directos de ``account.move.line`` porque su ORM permite que
CUALQUIER addon reabra esa clase (``_inherit``). Este ORM no tiene ese
mecanismo para nuevas columnas físicas sobre una tabla ajena sin escribir en
el app que la posee (ver arriba). El efecto observable — qué apuntes llevan
qué casillas fiscales — es idéntico; lo que cambia es dónde vive el dato
mientras el motor de envoltura de ``account`` no exista. Cuando ese motor se
porte (persistiendo los tres campos directamente en ``account.move.line``
vía ``add_to_class`` + su migración en ``account/``, siguiendo el precedente
``account_fleet``), estas tres tablas quedan obsoletas y se retiran junto
con el ajuste de ``AccountUpdateTaxTagsWizard`` para leer los campos reales.
"""
import fields
import models


class AccountMoveLineTax(models.Model):
    """Impuesto aplicado a una línea base — puente de ``tax_ids``.

    Una fila = "esta línea de apunte lleva aplicado este impuesto", el dato
    que en la referencia el usuario selecciona sobre la línea de factura
    (Odoo ``account.move.line.tax_ids``, ``account_move_line.py:194-204``).
    """

    line = fields.Many2one(
        'account.AccountMoveLine', on_delete=models.CASCADE,
        related_name='update_tax_tags_applied_taxes',
        help_text='Apunte base sobre el que se aplica el impuesto (≙ Odoo '
                  'account.move.line.tax_ids, lado línea).',
    )
    tax = fields.Many2one(
        'account.AccountTax', on_delete=models.CASCADE,
        related_name='update_tax_tags_move_lines',
        help_text='Impuesto aplicado a la línea (≙ Odoo tax_ids, lado impuesto).',
    )

    class Meta:
        db_table = 'account_update_tax_tags_aml_tax_rel'
        constraints = [
            models.UniqueConstraint(
                fields=['line', 'tax'], name='account_update_tax_tags_aml_tax_uniq',
            ),
        ]
        verbose_name = 'Impuesto aplicado a un apunte (puente tax_ids)'
        verbose_name_plural = 'Impuestos aplicados a apuntes (puente tax_ids)'

    def __str__(self) -> str:
        return f'{self.line} ~ {self.tax}'


class AccountMoveLineTaxRepartition(models.Model):
    """Línea de reparto que originó un apunte — puente de ``tax_repartition_line_id``.

    Una fila = "este apunte ES la línea de impuesto generada por esta línea
    de reparto" (Odoo ``account.move.line.tax_repartition_line_id``,
    ``account_move_line.py:223-229``). ``line`` es único: un apunte tiene a
    lo sumo UNA línea de reparto que lo originó (mismo comportamiento que el
    ``Many2one`` de la referencia); una línea de reparto, en cambio, puede
    haber originado varios apuntes (una por documento).
    """

    line = models.OneToOneField(
        'account.AccountMoveLine', on_delete=models.CASCADE,
        related_name='update_tax_tags_repartition',
        help_text='El apunte de impuesto mismo (≙ Odoo tax_repartition_line_id, '
                  'leído desde el lado del apunte).',
    )
    repartition_line = fields.Many2one(
        'account.AccountTaxRepartitionLine', on_delete=models.CASCADE,
        related_name='update_tax_tags_originated_lines',
        help_text='Línea de reparto que generó este apunte de impuesto '
                  '(≙ Odoo tax_repartition_line_id, lado reparto).',
    )

    class Meta:
        db_table = 'account_update_tax_tags_aml_tax_repartition'
        verbose_name = 'Reparto que originó un apunte (puente tax_repartition_line_id)'
        verbose_name_plural = 'Repartos que originaron apuntes (puente tax_repartition_line_id)'

    def __str__(self) -> str:
        return f'{self.line} ← {self.repartition_line}'


class AccountMoveLineTag(models.Model):
    """Casilla fiscal vigente de un apunte — puente de ``tax_tag_ids``.

    Es la tabla que ``AccountUpdateTaxTagsWizard`` reescribe (Odoo
    ``account.move.line.tax_tag_ids``, ``account_move_line.py:230-238``):
    ``update_amls_tax_tags`` borra las filas de los apuntes afectados e
    inserta las que correspondan a la configuración vigente de impuestos.
    """

    line = fields.Many2one(
        'account.AccountMoveLine', on_delete=models.CASCADE,
        related_name='update_tax_tags_tags',
        help_text='Apunte que lleva la casilla (≙ Odoo tax_tag_ids, lado línea).',
    )
    tag = fields.Many2one(
        'account.AccountAccountTag', on_delete=models.CASCADE,
        related_name='update_tax_tags_move_lines',
        help_text='Casilla fiscal vigente en el apunte (≙ Odoo tax_tag_ids, lado casilla).',
    )

    class Meta:
        db_table = 'account_update_tax_tags_aml_tag_rel'
        constraints = [
            models.UniqueConstraint(
                fields=['line', 'tag'], name='account_update_tax_tags_aml_tag_uniq',
            ),
        ]
        verbose_name = 'Casilla fiscal vigente de un apunte (puente tax_tag_ids)'
        verbose_name_plural = 'Casillas fiscales vigentes de apuntes (puente tax_tag_ids)'

    def __str__(self) -> str:
        return f'{self.line} → {self.tag}'
