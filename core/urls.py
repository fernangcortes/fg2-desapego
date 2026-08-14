from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('item/<slug:slug>/', views.item_detail, name='item_detail'),
    path('upload/', views.upload_rapido, name='upload_rapido'),
    path('item/<int:item_id>/quick-delete/', views.quick_delete_item, name='quick_delete_item'),
]

