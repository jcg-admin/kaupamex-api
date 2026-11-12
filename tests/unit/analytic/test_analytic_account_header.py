"""Cabecera de ``account.analytic.account`` contra la de la fuente.

≙ ``odoo19c: addons/analytic/models/analytic_account.py:11-18``. Los siete
atributos de clase se portan todos (``atributos-de-clase-de-modelo.md``), y
``_name`` tiene que participar en el registro: un atributo homónimo que
``model_by_name`` no resuelve no es el nombre del modelo.
"""
from addons.analytic.models import AccountAnalyticAccount
from orm import models
from orm.registry import model_by_name


def test_the_model_resolves_by_its_source_name():
    assert model_by_name('account.analytic.account') is AccountAnalyticAccount


def test_the_class_attributes_are_the_source_ones():
    cls = AccountAnalyticAccount
    assert cls._name == 'account.analytic.account'
    assert cls._inherit == ['mail.thread']
    assert cls._description == 'Analytic Account'
    assert cls._order == 'plan_id, name asc'
    assert cls._check_company_auto is True
    assert cls._check_company_domain is models.check_company_domain_parent_of
    assert cls._rec_names_search == ['name', 'code']


def test_the_table_matches_the_source_name():
    assert AccountAnalyticAccount._meta.db_table == 'account_analytic_account'
