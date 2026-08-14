from django.urls import path
from . import views

app_name = 'ai_engine'

urlpatterns = [
    path('process/<int:item_id>/', views.process_item_ai_view, name='process_item'),
    path('serpapi-quota/', views.serpapi_quota_view, name='serpapi_quota'),
    path('search-title/', views.search_internet_products_view, name='search_title'),
]

