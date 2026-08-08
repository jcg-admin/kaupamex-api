"""Vistas — ``addons.account_test``.

Recurso CRUD parcial (colección + detalle + una acción), así que va como
``ViewSet`` con router — mismo criterio que
``addons.website.controllers.search_history.SearchHistoryViewSet`` (skill
``backend-drf``, tabla de estilos: "recurso CRUD" → ``ViewSet``/router).
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from addons.authz.permissions import CapabilityRequiredMixin
from addons.account_test.controllers.serializers import (
    AccountingAssertTestRunResultSerializer,
    AccountingAssertTestSerializer,
)
from addons.account_test.models.accounting_assert_test import AccountingAssertTest


class AccountingAssertTestViewSet(CapabilityRequiredMixin,
                                  mixins.ListModelMixin,
                                  mixins.RetrieveModelMixin,
                                  mixins.DestroyModelMixin,
                                  viewsets.GenericViewSet):
    """``accounting.assert.test`` — listar, ver, ejecutar, borrar.

    Sin ``create``/``update``: la ACL de la referencia da ``perm_create=0``
    y ``perm_write=0`` a AMBOS grupos (ni el admin de sistema puede crear o
    editar desde la UI) — ver ``security/__init__.py``. Se replica con
    ``http_method_names`` acotado, no con permisos: no hay forma de que
    ninguna capacidad autorice ``create``/``update`` porque los mixins ni
    siquiera están en la herencia.

    Una sola capacidad (``finance.diagnostics``, ``is_sensitive=True``)
    gatea las cuatro acciones — la asimetría lectura-amplia/borrado-
    restringido de la referencia se colapsa (divergencia declarada, ver
    ``models/accounting_assert_test.py``). Al ser ``is_sensitive``, ``run``
    y ``destroy`` (métodos no-``SAFE_METHODS``) exigen sesión reautenticada
    fresca vía ``HasCapability`` (DEC-12) — ``list``/``retrieve`` no.
    """

    required_capability = 'finance.diagnostics'
    queryset = AccountingAssertTest.objects.all()
    serializer_class = AccountingAssertTestSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        # ``_order = "sequence"`` de la referencia — ``Meta.ordering`` del
        # modelo ya lo fija, pero se repite aquí porque `get_queryset` es
        # explícito y no depende de que el modelo no lo cambie por error.
        return AccountingAssertTest.objects.all().order_by('sequence', 'id')

    @extend_schema(
        tags=['finance'],
        summary='Listar pruebas de consistencia contable',
        responses={200: AccountingAssertTestSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['finance'],
        summary='Ver una prueba de consistencia contable',
        responses={200: AccountingAssertTestSerializer,
                   404: OpenApiResponse(description='No existe')},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['finance'],
        summary='Borrar una prueba de consistencia contable',
        responses={204: OpenApiResponse(description='Borrada')},
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['finance'],
        summary='Ejecutar una prueba de consistencia contable',
        request=None,
        responses={
            200: AccountingAssertTestRunResultSerializer,
            400: OpenApiResponse(description='ACCOUNT_TEST_INVALID_CODE — '
                                              'code_exec no compiló o usa '
                                              'una construcción prohibida'),
        },
    )
    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """≙ el botón *Imprimir* de la referencia — ejecuta ``code_exec`` y
        devuelve el veredicto. Sin PDF: ver la sección "``report`` →
        ``controllers``" en el docstring del modelo."""
        test = self.get_object()
        try:
            passed, lines = test.run()
        except (SyntaxError, NameError, ValueError) as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'ACCOUNT_TEST_INVALID_CODE'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = AccountingAssertTestRunResultSerializer({
            'id': test.pk,
            'name': test.name,
            'passed': passed,
            'result': lines,
        })
        return Response(serializer.data)
