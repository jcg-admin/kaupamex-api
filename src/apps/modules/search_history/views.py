"""
Views — apps.modules.search_history (UC-SRCH-03).

  GET    /api/v2/search/history/         20 latest entries for current user.
  DELETE /api/v2/search/history/         Alt-B: clear all.
  DELETE /api/v2/search/history/<id>/    Alt-A: delete single entry.

Owner isolation (RNF-SEC-003): a user can only see and delete their own.
Uses catalogue.SearchHistory as the backing model (same model populated
by the search view via _record_history_async).
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.modules.catalogue.models import SearchHistory


class _SearchHistorySerializer(serializers.ModelSerializer):
    searched_at = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = SearchHistory
        fields = ['id', 'term', 'searched_at']


class SearchHistoryListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='List search history (latest 20).',
        tags=['search'],
    )
    def get(self, request):
        qs = SearchHistory.objects.filter(user=request.user)[:20]
        return Response(_SearchHistorySerializer(qs, many=True).data)

    @extend_schema(summary='Clear search history.', tags=['search'],
                   operation_id='search_history_clear_all',
                   responses={204: None})
    def delete(self, request):
        SearchHistory.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SearchHistoryEntryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Delete a single search history entry.', tags=['search'],
                   operation_id='search_history_entry_destroy',
                   responses={204: None})
    def delete(self, request, pk):
        try:
            entry = SearchHistory.objects.get(pk=pk, user=request.user)
        except SearchHistory.DoesNotExist:
            raise NotFound({
                'detail': 'Entrada no encontrada.',
                'codigo_error': 'ENTRY_NOT_FOUND',
            })
        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
