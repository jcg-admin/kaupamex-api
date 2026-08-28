"""Campo de selección — fiel a ``odoo/orm/fields_selection.py`` (Odoo 19).

``Selection`` = ``CharField(choices=…)`` en Django.

Es un **despachador** de ``company_dependent`` (tarea #129), no un alias
pelado. El tipo está en ``COMPANY_DEPENDENT_FIELDS``
(``odoo19c: odoo/orm/fields.py:42-44``) y es el segundo más usado de la
referencia con **7** declaraciones, entre ellas
``analytic/models/analytic_plan.py:77`` (``default_applicability``), que es el
primero cableado aquí.

Con ``company_dependent=True`` el campo deja de ser ``varchar`` y pasa a ser
``jsonb``: ``choices`` y ``max_length`` no aplican a la columna y el
constructor de :class:`~orm.fields_company_dependent.CompanyDependent` los
descarta. La enumeración sigue siendo el contrato del valor —se valida en el
serializer y en ``clean``—, pero ya no la puede sostener una restricción de
columna, porque lo que la columna guarda es el mapa.
"""
from django.db import models

from orm.fields_company_dependent import make_dispatcher

__all__ = ['Selection']

# Odoo Selection ≈ CharField(choices=…)
Selection = make_dispatcher('Selection', 'selection', models.CharField)
