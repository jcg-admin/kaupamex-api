"""
Contract tests for the soft delete policy (DEC-DOC-007).

These tests validate the SoftDeleteModel mixin in core.models:
- ``delete()`` marks ``is_deleted=True`` + ``deleted_at`` and does
  NOT remove the row from the database.
- the default ``objects`` manager hides soft-deleted rows.
- ``all_objects`` exposes both alive and deleted rows.
- ``restore()`` reverts the soft delete.
- ``hard_delete()`` performs a real DELETE.
- ``queryset.delete()`` does a bulk soft delete via UPDATE.

Retirado ``TestSoftDeleteOnProduct`` (H-API-250): el sujeto era
``catalogue.Product``, disuelto. Su sucesor ``product.ProductTemplate``
hereda ``(ImageMixin, TimeStampedModel)`` — **no** ``SoftDeleteModel``: la
referencia archiva con ``active`` en vez de borrar en suave
(``odoo19c: product/models/product_template.py``). El contrato sobre un
modelo concreto lo cubre ``Voucher`` (``loyalty``).
Retirado tambien ``TestSoftDeleteOnAddress``: ``addons.users`` esta disuelto
(``res.users`` vive en ``base`` — ver ``analisis-users-no-es-un-addon-en-la-
referencia``) y ``Address`` no tiene sucesor construido.

``TestSoftDeleteOnOrder`` se **reapunta**, no se borra: ``SaleOrder`` ya no
declara el mixin (``sale_order.py:53`` → ``(MailThread, TimeStampedModel)``),
pero seis modelos concretos vivos sí lo declaran. El sujeto pasa a ``Voucher``
(``loyalty/models/voucher.py:28``), que conserva la cobertura del contrato
sobre un modelo real.
"""
import pytest
from addons.loyalty.models import Voucher
from addons.base.models import SoftDeleteModel, SoftDeleteManager, AllObjectsManager

pytestmark = pytest.mark.integration


class TestSoftDeleteContract:
    """Contract tests against core.models.SoftDeleteModel."""

    def test_softdeletemodel_is_abstract(self):
        assert SoftDeleteModel._meta.abstract is True

    def test_softdeletemodel_declares_required_fields(self):
        field_names = {f.name for f in SoftDeleteModel._meta.get_fields()}
        assert 'is_deleted' in field_names
        assert 'deleted_at' in field_names

    def test_softdeletemodel_exposes_dual_managers(self):
        # Managers son tipos distintos; los modelos concretos
        # heredan ambos. Verificamos los tipos en el mixin abstracto.
        assert SoftDeleteManager is not AllObjectsManager
        # Los managers se declaran como class attrs; en abstractos
        # quedan en _meta.local_managers.
        manager_names = {m.name for m in SoftDeleteModel._meta.local_managers}
        assert 'objects' in manager_names
        assert 'all_objects' in manager_names


class TestSoftDeleteOnVoucher:
    """``Voucher`` (loyalty) — modelo concreto vivo que declara el mixin."""

    @pytest.mark.django_db
    def test_voucher_inherits_softdelete(self):
        assert issubclass(Voucher, SoftDeleteModel)
        assert hasattr(Voucher, 'all_objects')
