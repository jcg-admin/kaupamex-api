"""
Soft-delete contract tests for apps.newsletter.NewsletterSubscriber (P-04).

DEC-DOC-007: NewsletterSubscriber inherits from SoftDeleteModel. Coexiste
con la semantica de NEGOCIO (status=UNSUBSCRIBED + unsubscribed_at).
"""
import pytest
from django.utils import timezone
from apps.newsletter.models import NewsletterSubscriber, SubscriberStatus
from apps.core.models import SoftDeleteModel

pytestmark = pytest.mark.integration


@pytest.fixture
def subscriber(db):
    return NewsletterSubscriber.objects.create(
        email='subs@example.com',
        status=SubscriberStatus.CONFIRMED,
        confirmed_at=timezone.now(),
    )


class TestNewsletterSubscriberSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        assert issubclass(NewsletterSubscriber, SoftDeleteModel)
        assert hasattr(NewsletterSubscriber, 'all_objects')

    @pytest.mark.django_db
    def test_delete_hides_from_default_manager(self, subscriber):
        pk = subscriber.pk
        subscriber.delete()
        assert not NewsletterSubscriber.objects.filter(pk=pk).exists()
        ghost = NewsletterSubscriber.all_objects.get(pk=pk)
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None

    @pytest.mark.django_db
    def test_restore(self, subscriber):
        subscriber.delete()
        NewsletterSubscriber.all_objects.get(pk=subscriber.pk).restore()
        assert NewsletterSubscriber.objects.filter(pk=subscriber.pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_removes(self, subscriber):
        pk = subscriber.pk
        subscriber.hard_delete()
        assert not NewsletterSubscriber.all_objects.filter(pk=pk).exists()

    @pytest.mark.django_db
    def test_business_unsubscribe_and_system_delete_coexist(self, subscriber):
        """``unsubscribed_at`` (NEGOCIO) y ``deleted_at`` (SISTEMA) son
        campos independientes; pueden marcarse ambos en la misma fila."""
        now = timezone.now()
        subscriber.status = SubscriberStatus.UNSUBSCRIBED
        subscriber.unsubscribed_at = now
        subscriber.is_deleted = True
        subscriber.deleted_at = now
        subscriber.save()
        ghost = NewsletterSubscriber.all_objects.get(pk=subscriber.pk)
        assert ghost.status == SubscriberStatus.UNSUBSCRIBED
        assert ghost.unsubscribed_at is not None
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None
