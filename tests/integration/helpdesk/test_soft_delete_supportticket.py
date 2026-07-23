"""
Soft-delete contract tests for addons.helpdesk.SupportTicket (P-02).

DEC-DOC-007: SupportTicket inherits from SoftDeleteModel to preserve
support history referenced by SupportTicketReply via CASCADE.
"""
import pytest
from addons.helpdesk.models import SupportTicket
from addons.base.models import SoftDeleteModel

pytestmark = pytest.mark.integration


@pytest.fixture
def ticket(db, user):
    return SupportTicket.objects.create(
        user=user,
        subject='Issue X',
        body='Issue body description with detail',
        category=SupportTicket.Category.GENERAL,
        status=SupportTicket.Status.OPEN,
    )


class TestSupportTicketSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        assert issubclass(SupportTicket, SoftDeleteModel)
        assert hasattr(SupportTicket, 'all_objects')

    @pytest.mark.django_db
    def test_delete_hides_from_default_manager(self, ticket):
        pk = ticket.pk
        ticket.delete()
        assert not SupportTicket.objects.filter(pk=pk).exists()
        ghost = SupportTicket.all_objects.get(pk=pk)
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None

    @pytest.mark.django_db
    def test_restore(self, ticket):
        ticket.delete()
        SupportTicket.all_objects.get(pk=ticket.pk).restore()
        assert SupportTicket.objects.filter(pk=ticket.pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_removes(self, ticket):
        pk = ticket.pk
        ticket.hard_delete()
        assert not SupportTicket.all_objects.filter(pk=pk).exists()
