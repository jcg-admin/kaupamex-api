"""Los dos métodos de pago manuales — ≙ el ``data/`` de la referencia.

``odoo19c: addons/account/data/account_data.xml:129-138``: dos registros de
``account.payment.method``, «Manual Payment» con código ``manual``, uno
``inbound`` y otro ``outbound``. Son los que ``account.journal`` usa como
métodos por defecto de sus líneas (``_default_inbound_payment_methods``,
``odoo19c: addons/account/models/account_journal.py:59-63``).

Mismo mecanismo que ``account_check_printing.data.check_payment_method``: el
registro y su identificador externo, idempotente por ``(module, name)``,
sobre los modelos históricos porque corre en una migración. Los nombres van
verbatim en inglés: son datos de la referencia.
"""

#: ``(nombre del identificador, nombre, código, tipo)``, en el orden del XML.
MANUAL_PAYMENT_METHODS = (
    ('account_payment_method_manual_in', 'Manual Payment', 'manual',
     'inbound'),
    ('account_payment_method_manual_out', 'Manual Payment', 'manual',
     'outbound'),
)


def seed_manual_payment_methods(apps, alias):
    """Crea (o respeta) los dos métodos manuales y sus identificadores."""
    AccountPaymentMethod = apps.get_model('account', 'AccountPaymentMethod')
    IrModelData = apps.get_model('base', 'IrModelData')
    label = AccountPaymentMethod._meta.label
    methods = AccountPaymentMethod.objects.using(alias)
    seeded = []
    for xmlid, name, code, payment_type in MANUAL_PAYMENT_METHODS:
        row = IrModelData.objects.using(alias).filter(
            module='account', name=xmlid).first()
        method = (methods.filter(pk=row.res_id).first()
                  if row is not None else None)
        if method is None:
            method = methods.filter(code=code,
                                    payment_type=payment_type).first()
        if method is None:
            method = methods.create(name=name, code=code,
                                    payment_type=payment_type)
        IrModelData.objects.using(alias).update_or_create(
            module='account', name=xmlid,
            defaults={'model': label, 'res_id': method.pk, 'noupdate': True})
        seeded.append(method)
    return seeded
