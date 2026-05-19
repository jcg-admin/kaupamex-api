from django.urls import path

from .views import SearchHistoryEntryView, SearchHistoryListView

app_name = 'search_history'

urlpatterns = [
    path('history/',           SearchHistoryListView.as_view(),  name='list'),
    path('history/<int:pk>/',  SearchHistoryEntryView.as_view(), name='detail'),
]
