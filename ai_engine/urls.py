from django.urls import path
from . import views

app_name = 'ai_engine'

urlpatterns = [
    path('process/<int:item_id>/', views.process_item_ai_view, name='process_item'),
]
