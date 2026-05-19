from rest_framework import serializers

from .models import SearchEntry


class SearchEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model  = SearchEntry
        fields = ['id', 'query', 'normalized_query', 'results_count', 'created_at']
