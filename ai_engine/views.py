import json
import logging
import requests
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.core.files.base import ContentFile
from core.models import Item, ImagemItem
from .services import AIOrchestrator, SerpApiService, MarketSearchService

logger = logging.getLogger(__name__)


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


@staff_member_required
def search_internet_products_view(request):
    """
    Pesquisa em tempo real produtos e preços na internet correspondentes ao termo digitado no título.
    Exclusivo para administradores (evita consumo indevido de cotas de APIs por visitantes).
    """
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({
            "success": False,
            "query": query,
            "total": 0,
            "items": [],
            "suggestion": {}
        })

    resultado = MarketSearchService.search_internet_products(query)
    return JsonResponse(resultado)


@staff_member_required
def proxy_image_view(request):
    """
    Proxy seguro para carregamento e conversão de fotos externas da web para Blob/File no navegador,
    evitando bloqueios de CORS ao importar imagens do Google Shopping/Mercado Livre no cliente.
    Exclusivo para administradores.
    """
    url = request.GET.get('url', '').strip()
    if not url or not url.startswith('http'):
        return HttpResponse("URL inválida", status=400)

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
        }
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            content_type = r.headers.get('Content-Type', 'image/jpeg')
            resp = HttpResponse(r.content, content_type=content_type)
            resp['Access-Control-Allow-Origin'] = '*'
            resp['Cache-Control'] = 'public, max-age=86400'
            return resp
    except Exception as e:
        logger.warning(f"Erro ao obter imagem proxy ({url}): {e}")

    return HttpResponse("Falha ao carregar imagem", status=502)


@staff_member_required
def import_web_images_view(request):
    """
    Endpoint para persistir fotos selecionadas da web diretamente no banco de dados para um Item existente.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Método POST obrigatório"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        item_id = data.get('item_id')
        image_urls = data.get('images', [])

        item = get_object_or_404(Item, pk=item_id)
        imported = 0
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

        for idx, img_url in enumerate(image_urls):
            if not img_url or not img_url.startswith('http'):
                continue
            try:
                r = requests.get(img_url, headers=headers, timeout=8)
                if r.status_code == 200:
                    ext = "jpg"
                    if "png" in r.headers.get('Content-Type', ''):
                        ext = "png"
                    elif "webp" in r.headers.get('Content-Type', ''):
                        ext = "webp"

                    file_name = f"web_{item.slug or item.id}_{idx + 1}.{ext}"
                    has_cover = item.imagens.filter(principal=True).exists()

                    ImagemItem.objects.create(
                        item=item,
                        imagem=ContentFile(r.content, name=file_name),
                        ordem=item.imagens.count(),
                        principal=(not has_cover and idx == 0)
                    )
                    imported += 1
            except Exception as err:
                logger.warning(f"Erro ao importar foto remota {img_url}: {err}")

        return JsonResponse({
            "success": True,
            "imported": imported,
            "total_images": item.imagens.count()
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


