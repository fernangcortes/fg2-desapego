from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from core.models import Item, ConfiguracaoVendedor
from .formatters import (
    format_for_olx,
    format_for_mercadolivre,
    format_for_facebook,
    format_whatsapp_message
)


@staff_member_required
def export_modal_view(request, item_id):
    """
    Exibe tela/modal com os textos prontos para copiar e colar na OLX, Mercado Livre e Facebook.
    """
    item = get_object_or_404(Item, pk=item_id)
    seller_config = ConfiguracaoVendedor.get_solo()
    base_url = request.build_absolute_uri('/')

    olx_text = format_for_olx(item, base_url)
    ml_text = format_for_mercadolivre(item, base_url)
    fb_text = format_for_facebook(item, base_url)
    wa_data = format_whatsapp_message(item, seller_config, base_url)
    direct_link = f"{base_url.rstrip('/')}/item/{item.slug}/"

    return render(request, 'marketplace/export_modal.html', {
        'item': item,
        'olx_text': olx_text,
        'ml_text': ml_text,
        'fb_text': fb_text,
        'wa_data': wa_data,
        'direct_link': direct_link,
    })


@staff_member_required
def export_api_view(request, item_id, platform):
    """
    API rápida que retorna o texto formatado para cópia em 1 clique.
    """
    item = get_object_or_404(Item, pk=item_id)
    base_url = request.build_absolute_uri('/')

    if platform == 'olx':
        text = format_for_olx(item, base_url)
    elif platform == 'mercadolivre':
        text = format_for_mercadolivre(item, base_url)
    elif platform == 'facebook':
        text = format_for_facebook(item, base_url)
    elif platform == 'link':
        text = f"{base_url.rstrip('/')}/item/{item.slug}/"
    else:
        return JsonResponse({'error': 'Plataforma inválida.'}, status=400)

    return JsonResponse({'platform': platform, 'text': text})
