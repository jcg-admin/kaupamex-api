"""
Views — apps.search_history (UC-SRCH-03).

  GET    /api/v1/search/history/         20 latest entries for current user.
  DELETE /api/v1/search/history/         Alt-B: clear all.
  DELETE /api/v1/search/history/<id>/    Alt-A: delete single entry.

Owner isolation (RNF-SEC-003): a user can only see and delete their own.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SearchEntry
from .serializers import SearchEntrySerializer


class SearchHistoryListView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SearchEntrySerializer

    @extend_schema(
        summary='List search history (latest 20).',
        responses={200: SearchEntrySerializer(many=True)},
        tags=['search'],
    )
    def get(self, request):
        qs = SearchEntry.objects.filter(user=request.user)[:20]
        return Response(SearchEntrySerializer(qs, many=True).data)

    @extend_schema(summary='Clear search history.', tags=['search'])
    def delete(self, request):
        SearchEntry.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SearchHistoryEntryView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SearchEntrySerializer

    @extend_schema(summary='Delete a single search history entry.', tags=['search'])
    def delete(self, request, pk):
        try:
            entry = SearchEntry.objects.get(pk=pk, user=request.user)
        except SearchEntry.DoesNotExist:
            raise NotFound({
                'detail': 'Entrada no encontrada.',
                'codigo_error': 'ENTRADA_NO_ENCONTRADA',
            })
        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
