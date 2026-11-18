"""La secuencia de los pagos — ≙ el ``data/`` de la referencia.

``odoo19c: addons/account/data/ir_sequence.xml:4-10``: un registro de
``ir.sequence``, «Payment», con código ``account.payment``, prefijo ``PAY``,
relleno 5 y sin empresa, en un bloque ``noupdate``. De ella sale el número
de un pago (``_compute_name``,
``odoo19c: addons/account/models/account_payment.py:414``).

Mismo mecanismo que :mod:`.payment_methods`: el registro y su identificador
externo, idempotente por ``(module, name)``, sobre los modelos históricos
porque corre en una migración.

La secuencia es ``standard`` —el valor por defecto del campo— y numera con
una secuencia nativa de PostgreSQL que ``IrSequence.save`` crea al dar de
alta la fila. Los modelos históricos no pasan por ``save``: la nativa se
crea aquí si falta. **Divergencia de mecanismo:** la fuente carga el XML
una vez por el ORM; esta siembra se repite tras cada prueba transaccional y
tiene que ser idempotente también sobre la secuencia nativa.
"""

from django.db import connections

#: ``(nombre del identificador, nombre, código, prefijo, relleno)``.
PAYMENT_SEQUENCE = ('seq_account_payment', 'Payment', 'account.payment',
                    'PAY', 5)


def _native_sequence_exists(alias, seq_name):
    with connections[alias].cursor() as cursor:
        cursor.execute(
            'SELECT 1 FROM pg_class WHERE relkind = %s AND relname = %s',
            ['S', seq_name])
        return cursor.fetchone() is not None


def _create_native_sequence(alias, seq_name, number_increment, number_next):
    """≙ ``_create_sequence`` (``odoo19c: odoo/addons/base/models/
    ir_sequence.py:13-18``) sobre la conexión de la migración. El nombre lo
    produce ``'ir_sequence_%03d' % pk``, con un entero de la propia base."""
    connection = connections[alias]
    with connection.cursor() as cursor:
        cursor.execute(
            f'CREATE SEQUENCE {connection.ops.quote_name(seq_name)} '
            f'INCREMENT BY %s START WITH %s',
            [number_increment, number_next])


def seed_payment_sequence(apps, alias):
    """Crea (o respeta) la secuencia de pagos y su identificador."""
    IrSequence = apps.get_model('base', 'IrSequence')
    IrModelData = apps.get_model('base', 'IrModelData')
    xmlid, name, code, prefix, padding = PAYMENT_SEQUENCE
    sequences = IrSequence.objects.using(alias)
    row = IrModelData.objects.using(alias).filter(
        module='account', name=xmlid).first()
    sequence = (sequences.filter(pk=row.res_id).first()
                if row is not None else None)
    if sequence is None:
        sequence = sequences.filter(code=code, company__isnull=True).first()
    if sequence is None:
        sequence = sequences.create(name=name, code=code, prefix=prefix,
                                    padding=padding)
    if sequence.implementation == 'standard':
        seq_name = 'ir_sequence_%03d' % sequence.pk
        if not _native_sequence_exists(alias, seq_name):
            _create_native_sequence(alias, seq_name,
                                    sequence.number_increment,
                                    sequence.number_next)
    IrModelData.objects.using(alias).update_or_create(
        module='account', name=xmlid,
        defaults={'model': IrSequence._meta.label, 'res_id': sequence.pk,
                  'noupdate': True})
    return sequence
