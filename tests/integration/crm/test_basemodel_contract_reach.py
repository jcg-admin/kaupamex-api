"""Contratos de ``BaseModel`` que llegan a ``crm.lead`` sin heredar de ella.

``crm.lead`` no es subclase de ``orm.models.BaseModel``: sus bases son
``MailThread``, ``MailActivityMixin``, ``UtmMixin``,
``FormatAddressMixin`` y ``TimeStampedModel``. Que no herede no prueba que no
reciba los contratos: ``TimeStampedModel`` adopta los mixins de ``src/orm``,
y ``adopt_access_manager`` le pone un manager cuyo queryset delega en
``AccessQuerySet``.

Cada prueba deriva su valor esperado de la referencia
(``odoo19c: odoo/orm/models.py`` en ``odoo-tools@abe4040e``), no del código
propio, y nombra la alteración que la hace caer.
"""
import pytest

from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.crm.models import CrmLead
from django.contrib.auth import get_user_model
from exceptions import AccessError, UserError

pytestmark = pytest.mark.integration

LABEL = CrmLead._meta.label


def _user(login):
    return get_user_model().objects.create_user(
        login=login, password='AlcancePrueba123!')


class TestOrderClauseCheckReachesTheLead:
    """``_check_qorder`` (``models.py:5215-5222``) por ``OrderMixin``.

    La fuente: ``if not regex_order.match(word): raise UserError(...)``.
    Mutación que la hace caer: retirar el ``raise`` de
    ``OrderMixin._check_qorder``; cae la segunda prueba.
    """

    def test_a_valid_clause_passes(self, db):
        lead = CrmLead.objects.create(name='Orden válido')
        assert lead._check_qorder('name desc, id') is None

    def test_an_injected_clause_is_rejected(self, db):
        lead = CrmLead.objects.create(name='Orden inyectado')
        with pytest.raises(UserError):
            lead._check_qorder('name; DROP TABLE crm_lead')


class TestAccessCheckReachesTheLeadThroughItsManager:
    """``check_access`` (``models.py:4100-4115``) delegado en
    ``AccessQuerySet``.

    La fuente: sin elevación, si ``_check_access`` devuelve un par se levanta
    su error. Mutación que la hace caer: un ``_check_access`` que devuelve
    ``None``; cae la primera prueba y la de control sigue verde.
    """

    def test_a_user_without_model_permission_is_refused(self, db):
        assert not IrModelAccess.objects.filter(
            model_id__model=LABEL).exists(), 'precondición: sin ACL'
        lead = CrmLead.objects.create(name='Sin permiso')
        who = _user('alcance.sin.acl@kaupamex.mx')
        with pytest.raises(AccessError):
            CrmLead.objects.filter(pk=lead.pk).check_access('read', user=who)

    def test_control_a_global_read_grant_lets_the_user_read(self, db):
        row, _ = IrModel.objects.get_or_create(
            model=LABEL, defaults={'name': 'Iniciativa'})
        IrModelAccess.objects.create(
            name='alcance lectura global', model_id=row, perm_read=True)
        lead = CrmLead.objects.create(name='Con permiso')
        who = _user('alcance.con.acl@kaupamex.mx')
        assert CrmLead.objects.filter(pk=lead.pk).check_access(
            'read', user=who) is None


class TestDisplayNameReachesTheLead:
    """``_compute_display_name`` (``models.py:1425-1439``) por
    ``DisplayNameMixin``.

    La fuente: con ``_rec_name`` el valor de ese campo pasado por
    ``convert_to_display_name``; ``crm.lead`` lo resuelve a ``name``.
    Mutación que la hace caer: devolver siempre ``modelo,id``.
    """

    def test_the_label_is_the_name(self, db):
        lead = CrmLead.objects.create(name='Etiqueta de la iniciativa')
        assert lead._compute_display_name() == 'Etiqueta de la iniciativa'
        assert lead.display_name == 'Etiqueta de la iniciativa'
