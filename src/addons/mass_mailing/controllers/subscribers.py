"""Vistas admin de suscriptores de la newsletter (UC-NEW-03).

Listar / exportar CSV / dar de baja (POST y DELETE) sobre la lista canónica
``"Newsletter"`` vía ``services``.
"""
import csv
import io

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from config.schema import error_response

from addons.mass_mailing import services as mm
from addons.mass_mailing.controllers.serializers import SubscriberListItemSerializer
from .base import _AdminOnly


class SubscriberPagination(PageNumberPagination):
    """H-CICLO43-03: paginacion para listado admin de suscriptores.
    Sin paginacion, devolver todos los suscriptores en una sola respuesta
    puede suponer miles de filas y un timeout/OOM en produccion."""
    page_size            = 50
    page_size_query_param = 'page_size'
    max_page_size        = 200


class AdminSubscriberListView(_AdminOnly, APIView):
    """GET /api/v2/admin/newsletter/subscribers/ — UC-NEW-03."""

    @extend_schema(
        summary='Listar suscriptores (UC-NEW-03)',
        tags=['newsletter'],
        responses={200: SubscriberListItemSerializer(many=True)},
    )
    def get(self, request):
        qs = mm.list_subscriptions(request.query_params.get('status'))
        paginator = SubscriberPagination()
        page = paginator.paginate_queryset(qs, request)
        data = [mm.serialize_item(sub) for sub in page]
        return paginator.get_paginated_response(data)


class AdminSubscriberExportCSVView(_AdminOnly, APIView):
    """GET /api/v2/admin/newsletter/subscribers/export/ — UC-NEW-03 (T-010).

    Exporta la lista de suscriptores como ``text/csv`` con los datos mínimos
    GDPR (Alt C del UC): email, estado y fecha de suscripción. Reusa el filtro
    ``status`` del listado pero sin paginar.
    """

    @extend_schema(
        summary='Exportar suscriptores a CSV (UC-NEW-03)',
        tags=['newsletter'],
        parameters=[
            OpenApiParameter('status', str, required=False,
                             description='PENDING / CONFIRMED / UNSUBSCRIBED'),
        ],
    )
    def get(self, request):
        qs = mm.list_subscriptions(
            request.query_params.get('status'),
        ).order_by('created_at', 'id')

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['email', 'estado', 'fecha_suscripcion'])
        for sub in qs.iterator():
            writer.writerow([
                sub.contact.email, mm.status_of(sub), sub.created_at.isoformat(),
            ])

        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = (
            'attachment; filename="newsletter_subscribers.csv"'
        )
        return response


class AdminSubscriberForceUnsubscribeView(_AdminOnly, APIView):
    """POST /api/v2/admin/newsletter/subscribers/<id>/unsubscribe/ — UC-NEW-03."""

    @extend_schema(
        summary='Dar de baja suscriptor (admin) (UC-NEW-03)',
        tags=['newsletter'],
        request=None,
        responses={200: SubscriberListItemSerializer,
                   404: error_response('Suscriptor no encontrado')},
    )
    def post(self, request, subscriber_id):
        sub = mm.list_subscriptions().filter(pk=subscriber_id).first()
        if not sub:
            raise NotFound({'detail': 'Suscriptor no encontrado.',
                            'codigo_error': 'SUBSCRIBER_NOT_FOUND'})
        mm.unsubscribe(sub)
        return Response(mm.serialize_item(sub))


class AdminSubscriberSubscriptionDeleteView(_AdminOnly, APIView):
    """DELETE /api/v2/admin/newsletter/subscribers/<id>/subscription/ — UC-NEW-03.

    REST-style alias for AdminSubscriberForceUnsubscribeView at /unsubscribe/.
    The UI (F5 Tier B) uses DELETE to /subscription/ instead of POST /unsubscribe/.
    """

    @extend_schema(
        summary='Dar de baja suscriptor via DELETE (admin) (UC-NEW-03)',
        tags=['newsletter'],
        request=None,
        responses={200: SubscriberListItemSerializer,
                   404: error_response('Suscriptor no encontrado')},
    )
    def delete(self, request, subscriber_id):
        return AdminSubscriberForceUnsubscribeView().post(
            request, subscriber_id=subscriber_id,
        )
