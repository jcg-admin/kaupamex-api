"""Un ``Many2one`` sin ``null=`` es opcional — ≙ ``required`` falso salvo
declaración (``odoo19c: odoo/orm/fields_relational.py:282``).

Antes la fachada heredaba el ``null=False`` de ``ForeignKey`` y la columna
salía ``NOT NULL`` por omisión (H-API-1122). La política ``ON DELETE`` que la
fuente deriva sigue a ``required``: ``set null`` si es opcional, ``restrict``
si es requerido.
"""

from django.db import models

import fields


def test_without_null_the_many2one_is_optional():
    field = fields.Many2one('base.ResPartner')
    assert field.null is True and field.blank is True
    assert field.ondelete == 'set null'
    assert field.remote_field.on_delete is models.SET_NULL


def test_null_false_declares_it_required():
    field = fields.Many2one('base.ResPartner', null=False)
    assert field.null is False
    assert field.ondelete == 'restrict'
    assert field.remote_field.on_delete is models.RESTRICT


def test_a_declared_on_delete_is_kept():
    field = fields.Many2one('base.ResPartner', on_delete=models.CASCADE)
    assert field.null is True
    assert field.remote_field.on_delete is models.CASCADE
