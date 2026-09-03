"""Que hace HOY el motor si un campo M2M declara ``compute=``.

Sonda de conducta, no de codigo: declara el campo, marca el registro y pide el
volcado, y anota donde revienta. Sin ella, «el M2M no cabe en el motor» es una
lectura del cuerpo de ``_flush``, no una medicion.
"""
import django
import os
import sys

sys.path.insert(0, 'src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()

from django.apps import apps                                      # noqa: E402
from orm.environments import env, transaction_scope               # noqa: E402
from orm.utils import model_field_registry                        # noqa: E402

AccountAccount = apps.get_model('account', 'AccountAccount')


def report(label, fn):
    try:
        out = fn()
    except Exception as error:                                    # noqa: BLE001
        print(f'{label}: {type(error).__name__}: {error}')
    else:
        print(f'{label}: {out!r}')


campo = AccountAccount._meta.get_field('tags')
registro = model_field_registry(AccountAccount)

print(f'many_to_many        : {campo.many_to_many}')
print(f'compute declarado   : {getattr(campo, "compute", None)!r}')
print(f'store               : {getattr(campo, "store", None)!r}')
print(f'attname             : {getattr(campo, "attname", None)!r}')
print(f'esta en el registro : {"tags" in registro}')
report('setattr sobre el M2M',
       lambda: setattr(AccountAccount(), 'tags', []))
report('update_fields con el M2M',
       lambda: AccountAccount(code='x', name='y').save(update_fields=['tags']))
