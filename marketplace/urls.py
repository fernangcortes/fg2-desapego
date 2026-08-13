from django.urls import path
from . import views

app_name = 'marketplace'

urlpatterns = [
    path('export/<int:item_id>/', views.export_modal_view, name='export_modal'),
    path('export/<int:item_id>/<str:platform>/', views.export_api_view, name='export_api'),
]
