"""El método de pago semilla «Checks» — ≙ el ``data/`` de la referencia.

``odoo19c: addons/account_check_printing/data/account_check_printing_data.xml``
(``odoo-tools@622ddc2a``, LGPL-3):

.. code-block:: xml

    <record id="account_payment_method_check" model="account.payment.method"
            noupdate="1">
        <field name="name">Checks</field>
        <field name="code">check_printing</field>
        <field name="payment_type">outbound</field>
    </record>

Un único registro de ``account.payment.method`` (modelo ya existente en
``account``, no se agrega columna alguna) más su identificador externo
(``ir.model.data``, tabla de ``base``) — mismo patrón que
``account_fleet.data.fleet_service_types`` (que a su vez sigue el de
``account.data.account_tags``).

El segundo ``<record>`` de la referencia (``ir.actions.server``
``action_account_print_checks``, que llama ``records.print_checks()`` desde
el cliente web) NO se porta — es navegación pura del cliente web de Odoo
(mismo criterio que ``models/account_journal.py``, Divergencia 3: sin
DRF-view en este pase). La capacidad que invocaría
(``CheckPrintingPaymentInfo.prepare_print_checks``) SÍ está portada.

**Los nombres van verbatim en inglés** — "Checks" es el dato copiado de la
referencia (mismo criterio que ``account/data/account_tags.py``: son datos,
no cadenas de interfaz de este puerto).
"""
#: Nombre del identificador externo, sin el módulo — ≙ el ``id`` del
#: ``<record>`` de la referencia.
CHECK_PAYMENT_METHOD_XMLID_NAME = 'account_payment_method_check'

#: Identificador externo completo, tal como lo citaría el código de este
#: addon (``account_check_printing.account_payment_method_check``).
CHECK_PAYMENT_METHOD_XMLID = f'account_check_printing.{CHECK_PAYMENT_METHOD_XMLID_NAME}'

#: Los tres campos del ``<record>`` de la referencia.
CHECK_PAYMENT_METHOD_NAME = 'Checks'
CHECK_PAYMENT_METHOD_CODE = 'check_printing'
CHECK_PAYMENT_METHOD_PAYMENT_TYPE = 'outbound'


def seed_check_payment_method(apps, alias):
    """Crea (o respeta) el método de pago «Checks» y su identificador externo.

    Escribe sobre los modelos **históricos** (``apps.get_model``) porque
    corre dentro de una migración — mismo criterio que
    ``account.data.account_tags.seed_account_tags``: ejecutar comportamiento
    de la app viva desde una migración la ata a un estado del código que
    cambia bajo sus pies.

    Idempotente por ``(module, name)`` de ``ir.model.data`` — un segundo
    pase repunta la fila en vez de duplicarla (``noupdate=True``, ≙
    ``noupdate="1"`` del XML original).
    """
    AccountPaymentMethod = apps.get_model('account', 'AccountPaymentMethod')
    IrModelData = apps.get_model('base', 'IrModelData')
    label = AccountPaymentMethod._meta.label

    row = IrModelData.objects.using(alias).filter(
        module='account_check_printing', name=CHECK_PAYMENT_METHOD_XMLID_NAME).first()
    existing = None
    if row is not None:
        existing = AccountPaymentMethod.objects.using(alias).filter(pk=row.res_id).first()
    if existing is None:
        existing = AccountPaymentMethod.objects.using(alias).filter(
            code=CHECK_PAYMENT_METHOD_CODE,
            payment_type=CHECK_PAYMENT_METHOD_PAYMENT_TYPE).first()
    if existing is None:
        existing = AccountPaymentMethod.objects.using(alias).create(
            name=CHECK_PAYMENT_METHOD_NAME,
            code=CHECK_PAYMENT_METHOD_CODE,
            payment_type=CHECK_PAYMENT_METHOD_PAYMENT_TYPE)
    IrModelData.objects.using(alias).update_or_create(
        module='account_check_printing', name=CHECK_PAYMENT_METHOD_XMLID_NAME,
        defaults={'model': label, 'res_id': existing.pk, 'noupdate': True},
    )
    return existing


def seed_bank_journal_check_sequences(apps, alias):
    """Da de alta la secuencia de cheques en los diarios de banco YA
    existentes — ≙ el ``post_init_hook`` de la referencia
    (``create_check_sequence_on_bank_journals``,
    ``odoo19c: __init__.py:7-8``): ``AccountJournal.search([('type', '=',
    'bank')])._create_check_sequence()``.

    Django no tiene gancho de post-instalación — el análogo es esta
    migración de datos (backfill de una sola vez). Los diarios de banco
    creados DESPUÉS la cubre la señal ``post_save`` que conecta
    ``AccountCheckPrintingConfig.ready()`` (ver
    ``models/account_journal.py::on_journal_saved``).
    """
    AccountJournal = apps.get_model('account', 'AccountJournal')
    IrSequence = apps.get_model('base', 'IrSequence')
    CheckPrintingJournalSettings = apps.get_model(
        'account_check_printing', 'CheckPrintingJournalSettings')

    for journal in AccountJournal.objects.using(alias).filter(type='bank'):
        settings, _created = CheckPrintingJournalSettings.objects.using(alias).get_or_create(
            journal=journal)
        if settings.sequence_id:
            continue
        sequence = IrSequence.objects.using(alias).create(
            name=f'{journal.name}: Check Number Sequence',
            implementation='no_gap', padding=5, number_increment=1,
            company=journal.company,
        )
        settings.sequence = sequence
        settings.save(using=alias, update_fields=['sequence'])
