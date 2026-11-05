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
from addons.crm.models import CrmLead, CrmLostReason
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


class TestWriteReachesTheLead:
    """``write`` (``models.py:4334-4353``) por ``RecordLoaderMixin``.

    La fuente rechaza un nombre que no es campo con ``ValueError("Invalid
    field ...")`` antes de escribir nada, y devuelve ``True``. Mutaciones que
    la hacen caer: retirar la comprobación del nombre (cae la primera) o
    devolver el registro (cae la segunda).
    """

    def test_a_name_that_is_not_a_field_is_rejected(self, db):
        lead = CrmLead.objects.create(name='Nombre ajeno')
        with pytest.raises(ValueError, match='Invalid field'):
            lead.write({'name': 'No se escribe', 'no_such_field': 1})
        lead.refresh_from_db()
        assert lead.name == 'Nombre ajeno', 'nada se escribe antes del error'

    def test_the_write_returns_true(self, db):
        lead = CrmLead.objects.create(name='Retorno')
        assert lead.write({'name': 'Retorno escrito'}) is True
        lead.refresh_from_db()
        assert lead.name == 'Retorno escrito'


class TestArchiveReachesTheLead:
    """``action_archive`` / ``action_unarchive`` / ``toggle_active``
    (``models.py:5790-5817``) por ``ArchiveMixin``.

    La fuente filtra los activos (o archivados) y les escribe el campo por
    ``write``. Mutación que la hace caer: un ``action_archive`` que no escribe;
    caen la primera y la de ``toggle_active``.
    """

    def test_archiving_an_active_lead_clears_active(self, db):
        lead = CrmLead.objects.create(name='Archivar')
        lead.action_archive()
        lead.refresh_from_db()
        assert lead.active is False

    def test_unarchiving_an_archived_lead_sets_active(self, db):
        lead = CrmLead.objects.create(name='Desarchivar', active=False)
        lead.action_unarchive()
        lead.refresh_from_db()
        assert lead.active is True

    def test_toggle_inverts_active(self, db):
        lead = CrmLead.objects.create(name='Alternar')
        lead.toggle_active()
        lead.refresh_from_db()
        assert lead.active is False


class TestLeadUnarchiveComposesWithItsParent:
    """``crm.lead.action_unarchive`` (``odoo19c:
    addons/crm/models/crm_lead.py:1101-1110``).

    La fuente llama a ``super().action_unarchive()`` y, sólo para los que se
    reactivaron, borra el motivo de pérdida. Mutación que la hace caer: un
    ``ArchiveMixin.action_unarchive`` que no escribe; la iniciativa queda
    archivada.
    """

    def test_reactivating_clears_the_lost_reason(self, db):
        reason = CrmLostReason.objects.create(name='Precio')
        lead = CrmLead.objects.create(
            name='Perdida', active=False, lost_reason_id=reason)
        lead.action_unarchive()
        lead.refresh_from_db()
        assert lead.active is True
        assert lead.lost_reason_id is None

    def test_an_active_lead_keeps_its_lost_reason(self, db):
        reason = CrmLostReason.objects.create(name='Plazo')
        lead = CrmLead.objects.create(
            name='Activa', active=True, lost_reason_id=reason)
        lead.action_unarchive()
        lead.refresh_from_db()
        assert lead.lost_reason_id == reason
