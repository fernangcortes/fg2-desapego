from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from core.models import Item
from .services import AIOrchestrator, SerpApiService


@staff_member_required
def process_item_ai_view(request, item_id):
    """
    Endpoint para disparar o processamento de um item pela IA através do Admin ou HTMX.
    Suporta parâmetro ?serpapi=1 para ativar busca profunda via Google Lens SerpApi sob demanda.
    """
    item = get_object_or_404(Item, pk=item_id)
    use_serpapi = request.GET.get('serpapi') in ['1', 'true', 'True'] or request.POST.get('serpapi') in ['1', 'true', 'True']

    resultado = AIOrchestrator.process_item(item.id, use_serpapi=use_serpapi)

    # Anexa cota atualizada no resultado
    quota = SerpApiService.get_account_quota()
    resultado['serpapi_quota'] = quota

    modo_nome = "Google Lens Profundo (SerpApi)" if use_serpapi else "IA Padrão Gratuita"

    if resultado.get('success'):
        messages.success(request, f"Item '{item.titulo}' processado com sucesso via {modo_nome}!")
    else:
        messages.error(request, f"Erro ao processar item com IA: {resultado.get('error')}")

    # Se a requisição pedir JSON (ex: HTMX, Terminal JS ou fetch)
    if (
        request.headers.get('accept') == 'application/json' or
        'application/json' in request.headers.get('accept', '') or
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        request.GET.get('format') == 'json'
    ):
        return JsonResponse(resultado)

    # Redireciona de volta para a edição do item no Django Admin
    return redirect(f'/admin/core/item/{item.id}/change/')


@staff_member_required
def serpapi_quota_view(request):
    """
    Retorna a cota disponível de pesquisas na SerpApi (Google Lens).
    """
    quota = SerpApiService.get_account_quota()
    return JsonResponse(quota)
