"""
Tests — UC-SYS-03: scan_low_stock task (path periodico).

Usa mocks para evitar dependencias de modelos Product/ProductVariant
que requieren fixtures complejas. Verifica que el task delega
correctamente a _maybe_create_alert.
"""
from unittest.mock import patch, MagicMock, call
from apps.addons.inventory.tasks import scan_low_stock


class TestScanLowStock:

    @patch('apps.addons.inventory.tasks._maybe_create_alert')
    @patch('apps.addons.inventory.tasks.ProductVariant')
    @patch('apps.addons.inventory.tasks.Product')
    @patch('apps.addons.inventory.tasks.SiteSettings')
    def test_llama_alert_para_producto_bajo_umbral(
        self, mock_settings_cls, mock_product_cls, mock_variant_cls, mock_alert
    ):
        mock_settings = MagicMock()
        mock_settings.min_stock_threshold = 5
        mock_settings_cls.get_current.return_value = mock_settings

        mock_product = MagicMock()
        mock_product.stock = 3
        mock_product_cls.objects.filter.return_value = [mock_product]
        mock_variant_cls.objects.filter.return_value.select_related.return_value = []

        result = scan_low_stock()

        mock_alert.assert_called_once_with(mock_product, None, 3)
        assert result >= 1

    @patch('apps.addons.inventory.tasks._maybe_create_alert')
    @patch('apps.addons.inventory.tasks.ProductVariant')
    @patch('apps.addons.inventory.tasks.Product')
    @patch('apps.addons.inventory.tasks.SiteSettings')
    def test_llama_alert_para_variante_bajo_umbral(
        self, mock_settings_cls, mock_product_cls, mock_variant_cls, mock_alert
    ):
        mock_settings = MagicMock()
        mock_settings.min_stock_threshold = 5
        mock_settings_cls.get_current.return_value = mock_settings

        mock_product_cls.objects.filter.return_value = []

        mock_variant = MagicMock()
        mock_variant.stock = 2
        mock_variant_cls.objects.filter.return_value.select_related.return_value = [
            mock_variant
        ]

        result = scan_low_stock()

        mock_alert.assert_called_once_with(mock_variant.product, mock_variant, 2)
        assert result >= 1

    @patch('apps.addons.inventory.tasks._maybe_create_alert')
    @patch('apps.addons.inventory.tasks.ProductVariant')
    @patch('apps.addons.inventory.tasks.Product')
    @patch('apps.addons.inventory.tasks.SiteSettings')
    def test_no_llama_alert_cuando_no_hay_bajos(
        self, mock_settings_cls, mock_product_cls, mock_variant_cls, mock_alert
    ):
        mock_settings = MagicMock()
        mock_settings.min_stock_threshold = 5
        mock_settings_cls.get_current.return_value = mock_settings

        mock_product_cls.objects.filter.return_value = []
        mock_variant_cls.objects.filter.return_value.select_related.return_value = []

        result = scan_low_stock()

        mock_alert.assert_not_called()
        assert result == 0

    @patch('apps.addons.inventory.tasks._maybe_create_alert')
    @patch('apps.addons.inventory.tasks.ProductVariant')
    @patch('apps.addons.inventory.tasks.Product')
    @patch('apps.addons.inventory.tasks.SiteSettings')
    def test_retorna_conteo_de_items_escaneados(
        self, mock_settings_cls, mock_product_cls, mock_variant_cls, mock_alert
    ):
        mock_settings = MagicMock()
        mock_settings.min_stock_threshold = 5
        mock_settings_cls.get_current.return_value = mock_settings

        mock_product_cls.objects.filter.return_value = [MagicMock(stock=1), MagicMock(stock=2)]
        mock_variant_cls.objects.filter.return_value.select_related.return_value = [
            MagicMock(stock=3)
        ]

        result = scan_low_stock()
        assert result == 3
