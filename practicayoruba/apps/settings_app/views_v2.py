"""
Views v2 — apps.settings_app F5 (§2.9 pages).

Tier B: StaticPageStatusV2View — PATCH /admin/pages/<slug>/status/
         (v1 had POST /pages/<slug>/publish/).
Tier B: StaticPageRestorationV2View — POST /admin/pages/<slug>/restorations/
         (v1 had POST /pages/<slug>/versions/<v>/restore/ with version in path;
          v2 takes version from request body).
"""
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import StaticPagePublishView, StaticPageRestoreView


class StaticPageStatusV2View(APIView):
    """PATCH /api/v2/admin/pages/<slug>/status/ — Tier B.

    v1 used POST /pages/<slug>/publish/; v2 uses PATCH /pages/<slug>/status/.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, slug):
        return StaticPagePublishView().post(request, slug=slug)


class StaticPageRestorationV2View(APIView):
    """POST /api/v2/admin/pages/<slug>/restorations/ — Tier B.

    v1 had version number in URL path (/versions/<v>/restore/).
    v2 takes version from request body: {"version": N}.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, slug):
        version_raw = request.data.get('version')
        if version_raw is None:
            return Response(
                {'detail': 'version requerido.', 'codigo_error': 'VERSION_REQUIRED'},
                status=400,
            )
        try:
            version = int(version_raw)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'version debe ser un entero.', 'codigo_error': 'INVALID_VERSION'},
                status=400,
            )
        return StaticPageRestoreView().post(request, slug=slug, version=version)
