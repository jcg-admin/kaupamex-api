"""
Soft-delete contract tests for apps.modules.contact.ContactMessage (P-03).

DEC-DOC-007: ContactMessage inherits from SoftDeleteModel to preserve
audit trail (PII + commercial contact history).
"""
import pytest
from apps.modules.contact.models import ContactMessage
from apps.core.models import SoftDeleteModel

pytestmark = pytest.mark.integration


@pytest.fixture
def message(db):
    return ContactMessage.objects.create(
        name='Alice',
        email='alice@example.com',
        subject='Pregunta sobre envío',
        body='Hola, ¿cuanto tardan los envíos?',
    )


class TestContactMessageSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        assert issubclass(ContactMessage, SoftDeleteModel)
        assert hasattr(ContactMessage, 'all_objects')

    @pytest.mark.django_db
    def test_delete_hides_from_default_manager(self, message):
        pk = message.pk
        message.delete()
        assert not ContactMessage.objects.filter(pk=pk).exists()
        ghost = ContactMessage.all_objects.get(pk=pk)
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None

    @pytest.mark.django_db
    def test_restore(self, message):
        message.delete()
        ContactMessage.all_objects.get(pk=message.pk).restore()
        assert ContactMessage.objects.filter(pk=message.pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_removes(self, message):
        pk = message.pk
        message.hard_delete()
        assert not ContactMessage.all_objects.filter(pk=pk).exists()
