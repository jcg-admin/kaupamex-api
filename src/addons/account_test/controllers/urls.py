"""URLs — ``addons.account_test``.

Router — nunca ``.as_view({...})`` manual (regla dura del skill
``backend-drf``: el bind manual ignora las ``permission_classes`` de
``@action``). Prefijo del router SIN slash final.

**Pendiente de wiring** (fuera de este alcance — ver ``apps.py``): incluir
este módulo en ``config/urls.py``, p. ej.::

    path('api/v2/admin/finance/', include(
        ('addons.account_test.controllers.urls', 'account_test'),
        namespace='account_test_v2'))
"""
from rest_framework.routers import DefaultRouter

from addons.account_test.controllers.views import AccountingAssertTestViewSet

router = DefaultRouter()
router.register(
    r'accounting-assert-tests', AccountingAssertTestViewSet,
    basename='accounting-assert-test',
)

urlpatterns = router.urls
