"""
Price-sync new endpoint surface (P-17 / UC-CAT-12).

These thin wrappers expose the four operations at the exact URLs
required by the UI contract. They reuse the parsing / persistence
logic already implemented in views.py (ProductPriceSyncView /
ProductPriceSyncConfirmView) — no business logic duplicated.

  POST /api/v1/admin/price-sync/preview-csv/         multipart "file"
  POST /api/v1/admin/price-sync/apply-csv/           {"session_id": ...}
  POST /api/v1/admin/price-sync/preview-percentage/  {"pct": ...}
  POST /api/v1/admin/price-sync/apply-percentage/    {"session_id": ...}
  GET  /api/v1/admin/price-sync/template.csv
"""
import csv
import uuid
from decimal import Decimal
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from apps.platform.authz.permissions import HasCapability
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Product, ProductPriceHistory
from .views import ProductPriceSyncView, PRICE_SYNC_CACHE_TTL




class _AdminOnly:
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'catalogue.edit'
    serializer_class = serializers.Serializer


def _store_session(validas):
    session_id = str(uuid.uuid4())
    cache.set(f'price_sync:{session_id}', validas, PRICE_SYNC_CACHE_TTL)
    return session_id


def _apply_session(session_id, changed_by=None):
    validas = cache.get(f'price_sync:{session_id}')
    if validas is None:
        return None
    product_ids = [row['product_id'] for row in validas]
    products = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}
    updated = []
    # H-CICLO114-01: registrar ProductPriceHistory por cada precio cambiado.
    # La version anterior omitia crear entradas de auditoria, dejando los
    # cambios masivos de precio sin trazabilidad en /price-history/.
    history_entries = []
    # H-CICLO44-01: bulk_update bypassa auto_now=True — setear updated_at
    # explicitamente en cada objeto antes de bulk_update.
    now = timezone.now()
    with transaction.atomic():
        for row in validas:
            p = products.get(row['product_id'])
            if not p:
                continue
            old_price = p.price
            p.price = Decimal(row['new_price'])
            p.updated_at = now
            updated.append(p)
            if p.price != old_price:
                history_entries.append(ProductPriceHistory(
                    product=p,
                    old_price=old_price,
                    new_price=p.price,
                    source=ProductPriceHistory.PRICE_SYNC,
                    changed_by=changed_by,
                ))
        Product.objects.bulk_update(updated, ['price', 'updated_at'])
        if history_entries:
            ProductPriceHistory.objects.bulk_create(history_entries)
    cache.delete(f'price_sync:{session_id}')
    cache.delete_many([f'product:{p.pk}:detail' for p in updated])
    return updated


class PriceSyncPreviewCSVView(_AdminOnly, APIView):
    @extend_schema(
        summary='Preview price sync from CSV.',
        responses={200: OpenApiTypes.OBJECT, 400: None},
        tags=['admin-catalogue'],
    )
    def post(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response(
                {'detail': 'Se requiere el archivo CSV.',
                 'codigo_error': 'CSV_REQUIRED'}, status=400,
            )
        helper = ProductPriceSyncView()
        validas, invalidas = helper._parse_csv(csv_file)
        session_id = _store_session(validas)
        return Response({
            'session_id':    session_id,
            'valid_count':   len(validas),
            'invalid_count': len(invalidas),
            'preview':       validas[:50],
            'errors':        invalidas,
        })


class PriceSyncApplyCSVView(_AdminOnly, APIView):
    @extend_schema(
        summary='Apply price sync (CSV).',
        responses={200: OpenApiTypes.OBJECT, 400: None},
        tags=['admin-catalogue'],
    )
    def post(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response(
                {'detail': 'session_id requerido.',
                 'codigo_error': 'SESSION_ID_REQUIRED'}, status=400,
            )
        updated = _apply_session(session_id, changed_by=request.user)
        if updated is None:
            return Response({
                'detail': 'Sesion expirada o no encontrada.',
                'codigo_error': 'SESSION_EXPIRED',
            }, status=400)
        return Response({
            'updated_count': len(updated),
            'message': f'{len(updated)} precios actualizados correctamente.',
        })


class PriceSyncPreviewPercentageView(_AdminOnly, APIView):
    @extend_schema(
        summary='Preview percentage price sync.',
        responses={200: OpenApiTypes.OBJECT, 400: None},
        tags=['admin-catalogue'],
    )
    def post(self, request):
        try:
            # H-CICLO114-02: usar Decimal para pct desde el origen para que
            # _apply_percentage construya el multiplicador sin perdida de
            # precision por conversion float→Decimal.
            pct = Decimal(str(request.data.get('pct', 0)))
        except Exception:
            return Response(
                {'detail': 'pct debe ser un numero.',
                 'codigo_error': 'PCT_INVALID'}, status=400,
            )
        helper = ProductPriceSyncView()
        validas, _ = helper._apply_percentage(
            pct,
            request.data.get('category_id'),
            request.data.get('price_min'),
            request.data.get('price_max'),
        )
        session_id = _store_session(validas)
        return Response({
            'session_id':    session_id,
            'valid_count':   len(validas),
            'preview':       validas[:50],
            'pct':           pct,
        })


class PriceSyncApplyPercentageView(_AdminOnly, APIView):
    @extend_schema(
        summary='Apply percentage price sync.',
        responses={200: OpenApiTypes.OBJECT, 400: None},
        tags=['admin-catalogue'],
    )
    def post(self, request):
        return PriceSyncApplyCSVView().post(request)


class PriceSyncTemplateView(_AdminOnly, APIView):
    @extend_schema(
        summary='Download price sync CSV template.',
        responses={200: OpenApiResponse(description='CSV template file download.', response=OpenApiTypes.BINARY)},
        tags=['admin-catalogue'],
    )
    def get(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            'attachment; filename="price-sync-template.csv"'
        )
        response.write('﻿')  # Excel BOM
        writer = csv.writer(response)
        writer.writerow(['sku', 'name', 'price'])
        for p in (
            Product.objects
            .filter(is_active=True)
            .only('sku', 'name', 'price')
            .order_by('sku')
        ):
            writer.writerow([p.sku, p.name, str(p.price)])
        return response
