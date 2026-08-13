from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from core.models import Item
from .services import AIOrchestrator


@staff_member_required
def process_item_ai_view(request, item_id):
    """
    Endpoint para disparar o reprocessamento de um item pela IA através do Admin ou HTMX.
    """
    item = get_object_or_404(Item, pk=item_id)
    resultado = AIOrchestrator.process_item(item.id)

    if resultado.get('success'):
        messages.success(request, f"Item '{item.titulo}' processado pela IA com sucesso!")
    else:
        messages.error(request, f"Erro ao processar item com IA: {resultado.get('error')}")

    # Se a requisição pedir JSON (ex: HTMX ou fetch)
    if request.headers.get('accept') == 'application/json' or request.GET.get('format') == 'json':
        return JsonResponse(resultado)

    # Redireciona de volta para a edição do item no Django Admin
    return redirect(f'/admin/core/item/{item.id}/change/')
