"""
Views — addons.logistics (P-10 / UC-LOG-01..09).
"""
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from addons.authz.permissions import HasCapability
from rest_framework.response import Response
from rest_framework.views import APIView


class ShipmentGuidePagination(PageNumberPagination):
    """Paginacion para listado de guias de envio — H-CICLO29-03."""
    page_size             = 25
    page_size_query_param = 'page_size'
    max_page_size         = 100

logger = logging.getLogger('apps')

from addons.orders.models import Order, OrderStatusLog
from config.schema import error_response
from .models import CarrierRateCard, Courier, ShipmentEvent, ShipmentGuide
from .offers import build_offers
from .serializers import (
    BuyerShipmentGuideSerializer, CourierCreateUpdateSerializer, CourierSerializer,
    ShipmentGuideCreateSerializer, ShipmentGuideSerializer,
    ShipmentOfferRequestSerializer,
)


class _AdminOnly:
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'logistics.edit'


class LogisticsPanelView(_AdminOnly, APIView):
    @extend_schema(summary='Panel logístico (UC-LOG-01)', tags=['logistics'], responses={200: None})
    def get(self, request):
        courier_id_raw = request.query_params.get('courier_id')
        courier_filter = None
        if courier_id_raw is not None:
            try:
                courier_filter = int(courier_id_raw)
            except ValueError:
                return Response({'detail': 'courier_id inválido.', 'codigo_error': 'COURIER_ID_INVALID'}, status=400)

        group_a_qs = Order.objects.filter(status=Order.STATUS_IN_PREPARATION).select_related('address').prefetch_related('items')
        pending_pickup = []
        for order in group_a_qs:
            entry = {'order_id': order.id, 'order_number': order.order_number, 'status': order.status}
            try:
                addr = order.address
                entry['recipient_name'] = addr.recipient_name
                entry['city'] = addr.city
            except Exception:
                logger.warning('Order %s has no address record', order.id)
            pending_pickup.append(entry)

        guide_qs = ShipmentGuide.objects.filter(is_deleted=False).exclude(
            status=ShipmentGuide.STATUS_DELIVERED,
        ).exclude(status=ShipmentGuide.STATUS_CANCELLED).select_related('order', 'courier')
        if courier_filter:
            guide_qs = guide_qs.filter(courier_id=courier_filter)

        in_transit = []
        for guide in guide_qs:
            in_transit.append({
                'guide_id': guide.id, 'tracking_number': guide.tracking_number,
                'order_id': guide.order_id, 'order_number': guide.order.order_number,
                'courier_code': guide.courier.code, 'status': guide.status,
            })

        return Response({'group_a_count': len(pending_pickup), 'group_b_count': len(in_transit),
                         'pending_pickup': pending_pickup, 'in_transit': in_transit})


class CourierListCreateView(_AdminOnly, APIView):
    @extend_schema(summary='Listar couriers', tags=['logistics'],
                   responses={200: CourierSerializer(many=True)})
    def get(self, request):
        return Response(CourierSerializer(Courier.objects.all().order_by('name'), many=True).data)

    @extend_schema(summary='Crear courier', tags=['logistics'],
                   request=CourierCreateUpdateSerializer,
                   responses={201: CourierSerializer, 400: error_response('Datos inválidos')})
    def post(self, request):
        ser = CourierCreateUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(CourierSerializer(ser.save()).data, status=201)


class CourierDetailView(_AdminOnly, APIView):
    def _get(self, pk):
        try:
            return Courier.objects.get(pk=pk)
        except Courier.DoesNotExist:
            raise NotFound({'detail': 'Courier no encontrado.', 'codigo_error': 'COURIER_NOT_FOUND'})

    @extend_schema(summary='Actualizar courier', tags=['logistics'],
                   request=CourierCreateUpdateSerializer,
                   responses={200: CourierSerializer,
                              400: error_response('Datos inválidos'),
                              404: error_response('Courier no encontrado')})
    def patch(self, request, pk):
        courier = self._get(pk)
        ser = CourierCreateUpdateSerializer(courier, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(CourierSerializer(courier).data)

    @extend_schema(summary='Desactivar courier', tags=['logistics'],
                   request=None,
                   responses={200: inline_serializer(
                       'CourierDeactivateResponse',
                       {'deactivated': serializers.BooleanField()}),
                       404: error_response('Courier no encontrado')})
    def delete(self, request, pk):
        courier = self._get(pk)
        courier.is_active = False
        courier.save(update_fields=['is_active', 'updated_at'])
        return Response({'deactivated': True})


class ShipmentGuideListCreateView(_AdminOnly, APIView):
    @extend_schema(summary='Listar guías de envío', tags=['logistics'],
                   responses={200: ShipmentGuideSerializer(many=True)})
    def get(self, request):
        qs = ShipmentGuide.objects.filter(is_deleted=False).select_related('order', 'courier').order_by('-created_at')
        if request.query_params.get('order_id'):
            qs = qs.filter(order_id=request.query_params['order_id'])
        # H-CICLO29-03: sin paginacion este endpoint podia retornar todas
        # las guias del sistema en una sola respuesta. Paginado a 25/pagina.
        paginator = ShipmentGuidePagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(ShipmentGuideSerializer(page, many=True).data)

    @extend_schema(summary='Crear guía de envío', tags=['logistics'],
                   request=ShipmentGuideCreateSerializer,
                   responses={201: ShipmentGuideSerializer,
                              400: error_response('Datos inválidos'),
                              409: error_response('Ya existe una guía activa para la orden')})
    def post(self, request):
        ser = ShipmentGuideCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        order = data['order']

        # H-CICLO110-04: envolver la dedup check + guide create + order save
        # en un bloque atomic con select_for_update para evitar dos requests
        # concurrentes que ambos pasen el filtro GUIDE_ALREADY_EXISTS y creen
        # dos guías para la misma orden. También se crea OrderStatusLog para
        # la transición →SHIPPED, que antes quedaba sin registro de auditoría.
        with transaction.atomic():
            order_locked = Order.objects.select_for_update().get(pk=order.pk)
            # H-CICLO72-03: prevent duplicate active guides for the same order.
            if ShipmentGuide.objects.filter(order=order_locked, is_deleted=False).exists():
                return Response(
                    {
                        'detail': 'Ya existe una guía de envío activa para esta orden.',
                        'codigo_error': 'GUIDE_ALREADY_EXISTS',
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            previous_status = order_locked.status
            guide = ShipmentGuide.objects.create(
                order=order_locked, courier=data['courier'],
                tracking_number=data['tracking_number'], notes=data.get('notes', ''),
            )
            order_locked.status = Order.STATUS_SHIPPED
            order_locked.save(update_fields=['status', 'updated_at'])
            OrderStatusLog.objects.create(
                order=order_locked,
                previous_status=previous_status,
                new_status=Order.STATUS_SHIPPED,
                changed_by=request.user,
                notes=f'Guía de envío creada: {data["tracking_number"]}',
            )

        # H-CICLO46-02: re-fetch guide with select_related to avoid N+1 when
        # ShipmentGuideSerializer accesses guide.order.order_number (source FK)
        # and guide.courier (nested CourierSerializer).
        guide = ShipmentGuide.objects.select_related('order', 'courier').get(pk=guide.pk)
        return Response(ShipmentGuideSerializer(guide).data, status=201)


class AdminOrderGuideView(_AdminOnly, APIView):
    """GET la guía de envío de una orden por order_number (admin).

    La UI admin conoce el order_number, no el pk de la guía; este endpoint le
    permite cargar la guía existente (con su id) para luego actualizar estado
    o rastreo vía ShipmentGuideDetailView. 404 si la orden no tiene guía.
    """

    @extend_schema(summary='Guía de envío de una orden (admin)', tags=['logistics'],
                   responses={200: ShipmentGuideSerializer,
                              404: error_response('Orden o guía no encontrada')})
    def get(self, request, order_number):
        guide = (
            ShipmentGuide.objects
            .select_related('order', 'courier')
            .filter(order__order_number=order_number, is_deleted=False)
            .first()
        )
        if not guide:
            return Response(
                {'detail': 'La orden no tiene guía de envío.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'},
                status=404,
            )
        return Response(ShipmentGuideSerializer(guide).data)


class ShipmentGuideDetailView(_AdminOnly, APIView):
    VALID_STATUSES = {s[0] for s in ShipmentGuide.STATUSES}

    # H-CICLO82-02: maquina de estados de guias de envio.
    # Sin esta tabla cualquier status valido podia setearse desde
    # cualquier estado anterior — p.ej. CREATED → DELIVERED sin
    # pasar por IN_TRANSIT, lo que rompe el historial de eventos y
    # la logica de ConfirmDeliveryView.
    ALLOWED_TRANSITIONS = {
        ShipmentGuide.STATUS_CREATED:    [ShipmentGuide.STATUS_PICKED_UP,
                                          ShipmentGuide.STATUS_CANCELLED],
        ShipmentGuide.STATUS_PICKED_UP:  [ShipmentGuide.STATUS_IN_TRANSIT,
                                          ShipmentGuide.STATUS_INCIDENT,
                                          ShipmentGuide.STATUS_CANCELLED],
        ShipmentGuide.STATUS_IN_TRANSIT: [ShipmentGuide.STATUS_DELIVERED,
                                          ShipmentGuide.STATUS_INCIDENT,
                                          ShipmentGuide.STATUS_CANCELLED],
        ShipmentGuide.STATUS_INCIDENT:   [ShipmentGuide.STATUS_IN_TRANSIT,
                                          ShipmentGuide.STATUS_CANCELLED],
        # DELIVERED y CANCELLED son terminales — sin transiciones permitidas.
    }

    def _get_guide(self, pk):
        try:
            return ShipmentGuide.objects.select_related('order', 'courier').get(pk=pk, is_deleted=False)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guía no encontrada.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'})

    @extend_schema(summary='Detalle de guía de envío', tags=['logistics'],
                   responses={200: ShipmentGuideSerializer,
                              404: error_response('Guía no encontrada')})
    def get(self, request, pk):
        return Response(ShipmentGuideSerializer(self._get_guide(pk)).data)

    @extend_schema(summary='Actualizar guía (rastreo o estado)', tags=['logistics'],
                   request=ShipmentGuideSerializer,
                   responses={200: ShipmentGuideSerializer,
                              400: error_response('Estado o rastreo inválido'),
                              404: error_response('Guía no encontrada')})
    def patch(self, request, pk):
        guide = self._get_guide(pk)
        # UC-LOG-02: el PATCH soporta dos operaciones independientes —
        #   (a) actualizar el numero/URL de rastreo (UC-LOG-02 flujo principal +
        #       Alt A/B/C), y
        #   (b) avanzar el status segun la maquina de estados (UC-LOG-04/05).
        # Si la peticion trae 'tracking_number'/'tracking_url' pero no 'status',
        # se trata como registro de rastreo. Si trae 'status', se aplica la
        # transicion de estado (comportamiento previo, intacto).
        has_status = 'status' in request.data
        has_tracking = 'tracking_number' in request.data or 'tracking_url' in request.data

        if has_tracking and not has_status:
            return self._update_tracking(request, guide)

        return self._update_status(request, guide)

    def _update_tracking(self, request, guide):
        """UC-LOG-02: registrar/actualizar el numero de rastreo y la URL.

        EX-01 (formato invalido): se rechaza un tracking_number vacio; el resto
        de formatos se permite (el admin puede forzarlo).
        EX-02 (numero ya registrado en otra guia): se advierte vía el campo
        ``warning`` en la respuesta pero la operacion se permite (el admin
        confirma con ``confirm_duplicate=true`` si quiere silenciar el aviso).
        """
        update_fields = ['updated_at']
        warning = None
        previous_tracking = guide.tracking_number

        if 'tracking_number' in request.data:
            new_tracking = (request.data.get('tracking_number') or '').strip()
            if not new_tracking:
                return Response(
                    {'detail': 'tracking_number requerido.', 'codigo_error': 'TRACKING_REQUIRED'},
                    status=400,
                )
            # EX-02: mismo numero en otra guia activa (excluyendo esta).
            dup = ShipmentGuide.objects.filter(
                tracking_number=new_tracking, is_deleted=False,
            ).exclude(pk=guide.pk).exists()
            if dup and not request.data.get('confirm_duplicate'):
                warning = (
                    f'El numero de rastreo {new_tracking!r} ya existe en otra guia activa. '
                    f'Reenvie con confirm_duplicate=true para registrarlo de todos modos.'
                )
            guide.tracking_number = new_tracking
            update_fields.append('tracking_number')

        if 'tracking_url' in request.data:
            guide.tracking_url = (request.data.get('tracking_url') or '').strip()
            update_fields.append('tracking_url')

        guide.save(update_fields=update_fields)
        # Auditoria del cambio (Alt C: el historial conserva el numero anterior).
        ShipmentEvent.objects.create(
            guide=guide, status=guide.status,
            description=(
                f'Rastreo actualizado: {previous_tracking!r} → {guide.tracking_number!r}.'
                + (f' URL: {guide.tracking_url}' if guide.tracking_url else '')
            ),
            occurred_at=timezone.now(), recorded_by=request.user,
        )
        data = ShipmentGuideSerializer(guide).data
        if warning:
            data['warning'] = warning
        return Response(data)

    def _update_status(self, request, guide):
        new_status = request.data.get('status')
        if not new_status or new_status not in self.VALID_STATUSES:
            return Response({'detail': f'Estado inválido: {new_status!r}.', 'codigo_error': 'STATUS_INVALID'}, status=400)
        # H-CICLO82-02: validar transicion contra la maquina de estados.
        allowed = self.ALLOWED_TRANSITIONS.get(guide.status, [])
        if new_status not in allowed:
            return Response(
                {
                    'detail': (
                        f'Transición no permitida: {guide.status} → {new_status}. '
                        f'Transiciones válidas: {allowed or ["ninguna (estado terminal)"]}'
                    ),
                    'codigo_error': 'INVALID_STATUS_TRANSITION',
                },
                status=400,
            )
        guide.status = new_status
        guide.save(update_fields=['status', 'updated_at'])
        ShipmentEvent.objects.create(
            guide=guide, status=new_status,
            description=request.data.get('description', ''),
            occurred_at=timezone.now(), recorded_by=request.user,
        )
        return Response(ShipmentGuideSerializer(guide).data)


class ConfirmDeliveryView(_AdminOnly, APIView):
    @extend_schema(summary='Confirmar entrega de guía', tags=['logistics'],
                   request=None,
                   responses={200: inline_serializer(
                       'ConfirmDeliveryResponse',
                       {'status': serializers.CharField(),
                        'already_delivered': serializers.BooleanField(),
                        'tracking_number': serializers.CharField(),
                        'delivered_at': serializers.DateTimeField(required=False)}),
                       400: error_response('Guía cancelada'),
                       404: error_response('Guía no encontrada')})
    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order').get(pk=pk, is_deleted=False)
        except ShipmentGuide.DoesNotExist:
            return Response({'detail': 'Guía no encontrada.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'}, status=404)
        if guide.status == ShipmentGuide.STATUS_CANCELLED:
            return Response({'detail': 'Guía cancelada.', 'codigo_error': 'SHIPMENT_GUIDE_CANCELLED'}, status=400)
        if guide.status == ShipmentGuide.STATUS_DELIVERED:
            return Response({'status': guide.status, 'already_delivered': True, 'tracking_number': guide.tracking_number})
        # H-CICLO110-04: envolver guide.save + order.save en un bloque atomic
        # con select_for_update para prevenir:
        # (a) inconsistencia si el primer save commitea y el segundo falla
        #     (guide=DELIVERED pero order≠DELIVERED o viceversa).
        # (b) dos admins confirmando la misma guia concurrentemente, creando
        #     dos OrderStatusLog SHIPPED→DELIVERED.
        # Ademas se crea OrderStatusLog para la transicion SHIPPED→DELIVERED,
        # que antes quedaba sin entrada de auditoria.
        with transaction.atomic():
            guide_locked = ShipmentGuide.objects.select_for_update().select_related('order').get(pk=pk)
            if guide_locked.status == ShipmentGuide.STATUS_DELIVERED:
                return Response({'status': guide_locked.status, 'already_delivered': True,
                                 'tracking_number': guide_locked.tracking_number})
            previous_order_status = guide_locked.order.status
            now = timezone.now()
            guide_locked.status = ShipmentGuide.STATUS_DELIVERED
            guide_locked.delivered_at = now
            guide_locked.save(update_fields=['status', 'delivered_at', 'updated_at'])
            guide_locked.order.status = Order.STATUS_DELIVERED
            guide_locked.order.save(update_fields=['status', 'updated_at'])
            OrderStatusLog.objects.create(
                order=guide_locked.order,
                previous_status=previous_order_status,
                new_status=Order.STATUS_DELIVERED,
                changed_by=request.user,
                notes=f'Entrega confirmada via guia #{guide_locked.pk} ({guide_locked.tracking_number})',
            )
        return Response({'status': guide_locked.status, 'already_delivered': False,
                         'tracking_number': guide_locked.tracking_number,
                         'delivered_at': guide_locked.delivered_at})


class CancelGuideView(_AdminOnly, APIView):
    @extend_schema(summary='Cancelar guía de envío', tags=['logistics'],
                   request=None,
                   responses={200: inline_serializer(
                       'CancelGuideResponse',
                       {'cancelled': serializers.BooleanField(),
                        'tracking_number': serializers.CharField()}),
                       400: error_response('Guía entregada o ya cancelada'),
                       404: error_response('Guía no encontrada')})
    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order').get(pk=pk, is_deleted=False)
        except ShipmentGuide.DoesNotExist:
            return Response({'detail': 'Guía no encontrada.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'}, status=404)
        if guide.status == ShipmentGuide.STATUS_DELIVERED:
            return Response({'detail': 'No se puede cancelar una guía entregada.', 'codigo_error': 'SHIPMENT_GUIDE_DELIVERED'}, status=400)
        if guide.status == ShipmentGuide.STATUS_CANCELLED:
            return Response({'detail': 'La guía ya está cancelada.', 'codigo_error': 'SHIPMENT_GUIDE_ALREADY_CANCELLED'}, status=400)
        guide.status = ShipmentGuide.STATUS_CANCELLED
        guide.is_deleted = True
        guide.deleted_at = timezone.now()
        guide.save(update_fields=['status', 'is_deleted', 'deleted_at', 'updated_at'])
        return Response({'cancelled': True, 'tracking_number': guide.tracking_number})


class BuyerGuideView(APIView):
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.shipments'

    def _guide_response(self, request, order_lookup):
        """order_lookup: dict con pk o order_number, siempre scoped al usuario."""
        try:
            order = Order.objects.get(user=request.user, **order_lookup)
        except Order.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'}, status=404)
        guide = ShipmentGuide.objects.filter(order=order, is_deleted=False).select_related('courier').first()
        if not guide:
            return Response({'detail': 'Guía de envío no disponible.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'}, status=404)
        return Response(BuyerShipmentGuideSerializer(guide, context={'request': request}).data)

    @extend_schema(summary='Guía de envío del comprador (UC-LOG-06)', tags=['logistics'],
                   responses={200: BuyerShipmentGuideSerializer,
                              404: error_response('Orden o guía no encontrada')})
    def get(self, request, order_id):
        return self._guide_response(request, {'pk': order_id})


class BuyerGuideByNumberView(BuyerGuideView):
    """UC-LOG-06 por order_number: la UI del comprador conoce el order_number
    (no el PK entero, oculto por diseño), así que expone la misma guía por su
    identificador público."""

    @extend_schema(summary='Guía de envío del comprador por order_number', tags=['logistics'],
                   responses={200: BuyerShipmentGuideSerializer,
                              404: error_response('Orden o guía no encontrada')})
    def get(self, request, order_number):
        return self._guide_response(request, {'order_number': order_number})


class BuyerReportIncidentView(APIView):
    """UC-LOG-07: el comprador dueño reporta un problema de su envío.

    El reporte se materializa como (a) la guía pasa a estado INCIDENT y
    (b) un ShipmentEvent append-only que conserva el tipo de problema y la
    descripción del comprador (POST-01). Sigue el patrón owner-scoped de
    BuyerGuideView: la orden debe pertenecer al usuario autenticado o se
    devuelve 404 ORDER_NOT_FOUND (EX-01, RNF-SEC-003: no revela existencia).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.shipments'

    PROBLEM_TYPES = {'NOT_RECEIVED', 'DAMAGED_PRODUCT', 'WRONG_DELIVERY', 'DELAY'}
    MIN_DESCRIPTION_LEN = 20
    # Estados desde los que tiene sentido reportar un problema de envío: el
    # paquete ya salió (EX-02 rechaza reportar antes de que el envío avance).
    REPORTABLE_STATUSES = {
        ShipmentGuide.STATUS_PICKED_UP,
        ShipmentGuide.STATUS_IN_TRANSIT,
        ShipmentGuide.STATUS_DELIVERED,
        ShipmentGuide.STATUS_INCIDENT,
    }

    @extend_schema(
        summary='Reportar problema de envío (UC-LOG-07)', tags=['logistics'],
        request=inline_serializer('BuyerReportIncidentRequest', {
            'problem_type': serializers.ChoiceField(
                choices=sorted(PROBLEM_TYPES)),
            'description': serializers.CharField(min_length=MIN_DESCRIPTION_LEN),
        }),
        responses={201: None,
                   400: error_response('Payload inválido'),
                   404: error_response('Orden o guía no encontrada'),
                   409: error_response('Envío no despachado o reporte reciente existente')})
    def post(self, request, order_id=None, order_number=None):
        # La UI del comprador usa order_number (el PK entero se oculta); se
        # acepta cualquiera de los dos, siempre scoped al usuario.
        lookup = {'pk': order_id} if order_id is not None else {'order_number': order_number}
        try:
            order = Order.objects.get(user=request.user, **lookup)
        except Order.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'}, status=404)

        guide = ShipmentGuide.objects.filter(order=order, is_deleted=False).select_related('order').first()
        if not guide:
            return Response(
                {'detail': 'Guía de envío no disponible.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'},
                status=404,
            )

        problem_type = (request.data.get('problem_type') or '').strip()
        if problem_type not in self.PROBLEM_TYPES:
            return Response(
                {
                    'detail': f'problem_type inválido. Valores: {sorted(self.PROBLEM_TYPES)}.',
                    'codigo_error': 'INVALID_PAYLOAD',
                },
                status=400,
            )
        description = (request.data.get('description') or '').strip()
        if len(description) < self.MIN_DESCRIPTION_LEN:
            return Response(
                {
                    'detail': f'description requiere al menos {self.MIN_DESCRIPTION_LEN} caracteres.',
                    'codigo_error': 'INVALID_PAYLOAD',
                },
                status=400,
            )

        # EX-02: el paquete no ha salido aún → no se puede reportar problema de envío.
        if guide.status not in self.REPORTABLE_STATUSES:
            return Response(
                {
                    'detail': (
                        'No se puede reportar un problema de envío si el paquete no ha salido. '
                        f'Estado actual de la guía: {guide.status}.'
                    ),
                    'codigo_error': 'SHIPMENT_NOT_DISPATCHED',
                },
                status=409,
            )

        # 409 RECENT_REPORT_EXISTS: evitar reportes duplicados recientes del comprador.
        recent_cutoff = timezone.now() - timedelta(hours=24)
        if guide.events.filter(
            status=ShipmentGuide.STATUS_INCIDENT,
            recorded_by=request.user,
            created_at__gte=recent_cutoff,
        ).exists():
            return Response(
                {
                    'detail': 'Ya existe un reporte reciente para este envío.',
                    'codigo_error': 'RECENT_REPORT_EXISTS',
                },
                status=409,
            )

        with transaction.atomic():
            guide_locked = ShipmentGuide.objects.select_for_update().get(pk=guide.pk)
            now = timezone.now()
            if guide_locked.status != ShipmentGuide.STATUS_INCIDENT:
                guide_locked.status = ShipmentGuide.STATUS_INCIDENT
                guide_locked.save(update_fields=['status', 'updated_at'])
            event = ShipmentEvent.objects.create(
                guide=guide_locked,
                status=ShipmentGuide.STATUS_INCIDENT,
                description=f'[{problem_type}] {description}',
                occurred_at=now, recorded_by=request.user,
            )

        return Response(
            {
                'report_id': event.id,
                'status': 'RECEIVED',
                'problem_type': problem_type,
                'estimated_response_days': 3,
            },
            status=201,
        )


# ─── V2 views (UC-SRCH-03 F5 §1.3) ──────────────────────────────────────────

class ShipmentListCreateV2View(APIView):
    """GET|POST /api/v2/shipments/ — Tier A."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'logistics.edit'

    def get(self, request):
        return ShipmentGuideListCreateView().get(request)

    def post(self, request):
        return ShipmentGuideListCreateView().post(request)


class ShipmentDetailV2View(APIView):
    """GET|PATCH /api/v2/shipments/<pk>/ — Tier A."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'logistics.edit'

    def get(self, request, pk):
        return ShipmentGuideDetailView().get(request, pk)

    def patch(self, request, pk):
        return ShipmentGuideDetailView().patch(request, pk)


class ShipmentCancellationV2View(APIView):
    """POST /api/v2/shipments/<pk>/cancellations/ — Tier A."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'logistics.edit'

    def post(self, request, pk):
        return CancelGuideView().post(request, pk)


class ShipmentDeliveryV2View(APIView):
    """POST /api/v2/shipments/<pk>/deliveries/ — Tier A."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'logistics.edit'

    def post(self, request, pk):
        return ConfirmDeliveryView().post(request, pk)


class BuyerOrderShipmentV2View(APIView):
    """GET /api/v2/orders/<order_id>/shipment/ — Tier A."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.shipments'

    def get(self, request, order_id):
        return BuyerGuideView().get(request, order_id)


class ShipmentProblemReportV2View(APIView):
    """POST /api/v2/shipments/<pk>/problem-reports/ — Tier B.

    v1 used order_id in path; v2 is shipment-scoped. Resolve order_id
    from the guide before delegating. Ownership check (order.user ==
    request.user) happens inside BuyerReportIncidentView (EX-01).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.shipments'

    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order').get(
                pk=pk, is_deleted=False,
            )
        except ShipmentGuide.DoesNotExist:
            raise NotFound(
                {'detail': 'Envío no encontrado.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'}
            )
        return BuyerReportIncidentView().post(request, guide.order_id)


class ShipmentOffersView(_AdminOnly, APIView):
    """POST /api/v2/shipping-offers — motor de cotización de paqueterías.

    Recibe un envío (paquetes con dimensiones/peso/valor/peligrosidad),
    evalúa cada paquetería activa (``CarrierRateCard``) contra sus reglas
    de elegibilidad y devuelve las **elegibles** rankeadas (costo asc →
    tránsito asc → ambiental desc) más las **inelegibles** con el motivo.

    **Sólo admin** (``logistics.manage``). La elección de paquetería
    (DHL/FedEx/…) es una decisión del administrador, NO del comprador: el
    comprador nunca ve la lista de paqueterías, sólo el costo final de envío
    (por peso o por zona) que resuelve el checkout. Este endpoint expone la
    lista rankeada para la operación/administración. Validación DRF → HTTP 400.
    """

    @extend_schema(
        summary='Cotizar paqueterías para un envío (Shipment Offer API, admin)',
        tags=['logistics'],
        request=ShipmentOfferRequestSerializer,
        responses={200: None, 400: None},
    )
    def post(self, request):
        serializer = ShipmentOfferRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        packages = serializer.validated_data['packages']

        rate_cards = [
            rc.to_rate_card()
            for rc in CarrierRateCard.objects.filter(is_active=True)
                                             .select_related('courier')
        ]
        result = build_offers(packages, rate_cards)
        return Response(result, status=status.HTTP_200_OK)
