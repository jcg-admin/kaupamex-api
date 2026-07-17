"""
Soft-delete contract tests for addons.returns.ReturnRequest (P-08).
DEC-DOC-007: ReturnRequest debe preservar el rastro financiero
referenciado desde ReturnItem y ReturnHistoryEntry via CASCADE.
"""
import pytest
from addons.returns.models import ReturnRequest
from core.models import SoftDeleteModel

pytestmark = pytest.mark.integration


@pytest.fixture
def return_request(db, user):
    return ReturnRequest.objects.create(
        user=user,
        order_id=999,
        reason=ReturnRequest.Reason.DAMAGED_PRODUCT,
        description='Producto llegó dañado, caja rota.',
        status=ReturnRequest.Status.PENDING_REVIEW,
    )


class TestReturnRequestSoftDelete:

    @pytest.mark.django_db
    def test_inherits_softdeletemodel(self):
        assert issubclass(ReturnRequest, SoftDeleteModel)
        assert hasattr(ReturnRequest, 'all_objects')

    @pytest.mark.django_db
    def test_delete_hides_from_default_manager(self, return_request):
        pk = return_request.pk
        return_request.delete()
        assert not ReturnRequest.objects.filter(pk=pk).exists()
        ghost = ReturnRequest.all_objects.get(pk=pk)
        assert ghost.is_deleted is True
        assert ghost.deleted_at is not None

    @pytest.mark.django_db
    def test_restore(self, return_request):
        return_request.delete()
        ReturnRequest.all_objects.get(pk=return_request.pk).restore()
        assert ReturnRequest.objects.filter(pk=return_request.pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_removes(self, return_request):
        pk = return_request.pk
        return_request.hard_delete()
        assert not ReturnRequest.all_objects.filter(pk=pk).exists()
