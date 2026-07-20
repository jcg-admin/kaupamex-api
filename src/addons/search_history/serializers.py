from rest_framework import serializers
from addons.website.models import SearchEntry



class SearchEntrySerializer(serializers.ModelSerializer):
    """H-CICLO37-02: la UI (SearchHistoryPage.jsx) accede a ``term`` y
    ``searched_at`` pero el modelo SearchEntry almacena ``query`` y
    ``created_at``. Se exponen como aliases para mantener el contrato
    JSON que espera la UI sin renombrar la columna de base de datos.
    """

    term       = serializers.CharField(source='query', read_only=True)
    searched_at = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model  = SearchEntry
        fields = ['id', 'query', 'normalized_query', 'results_count', 'created_at',
                  'term', 'searched_at']
