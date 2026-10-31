"""Comprueba el fallo real oculto por el xfail heredado, sin modificar el test."""
import django
import pytest
django.setup()
raise SystemExit(pytest.main(['--confcutdir=tests/unit/orm','-o','addopts=',
 '--runxfail','--tb=short','-q','tests/unit/orm/test_sorted_order_to_function.py::TestTheRelationalBranches::test_a_many2one_recurses_into_the_comodel_order']))
