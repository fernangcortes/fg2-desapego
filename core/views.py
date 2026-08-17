from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, Http404, JsonResponse
from django.utils import timezone
from django.db.models import Q
from .models import Item, ImagemItem, ConfiguracaoVendedor
from marketplace.formatters import format_whatsapp_message


def home(request):
    """
    Vitrine Pública com filtros por tipo (Venda / Aluguel), categorias e busca textual.
    Exibe apenas itens com status 'Aprovado'.
    """
    configuracao = ConfiguracaoVendedor.get_solo()
    tipo_filtro = request.GET.get('tipo', 'todos')
    categoria_filtro = request.GET.get('categoria', '')
    busca = request.GET.get('q', '').strip()

    itens = Item.objects.filter(status=Item.Status.APROVADO)

    # Filtro por tipo de anúncio
    if tipo_filtro == 'venda':
        itens = itens.filter(tipo_anuncio__in=[Item.TipoAnuncio.VENDA, Item.TipoAnuncio.AMBOS])
    elif tipo_filtro == 'aluguel':
        itens = itens.filter(tipo_anuncio__in=[Item.TipoAnuncio.ALUGUEL, Item.TipoAnuncio.AMBOS])

    # Filtro por categoria
    if categoria_filtro and categoria_filtro in [c[0] for c in Item.Categoria.choices]:
        itens = itens.filter(categoria=categoria_filtro)

    # Busca textual
    if busca:
        itens = itens.filter(
            Q(titulo__icontains=busca) |
            Q(descricao_ia__icontains=busca) |
            Q(descricao_manual__icontains=busca) |
            Q(defeitos_visiveis__icontains=busca)
        )

    # Contadores para as abas
    total_aprovados = Item.objects.filter(status=Item.Status.APROVADO).count()
    total_venda = Item.objects.filter(status=Item.Status.APROVADO, tipo_anuncio__in=[Item.TipoAnuncio.VENDA, Item.TipoAnuncio.AMBOS]).count()
    total_aluguel = Item.objects.filter(status=Item.Status.APROVADO, tipo_anuncio__in=[Item.TipoAnuncio.ALUGUEL, Item.TipoAnuncio.AMBOS]).count()

    return render(request, 'core/home.html', {
        'configuracao': configuracao,
        'itens': itens,
        'tipo_filtro': tipo_filtro,
        'categoria_filtro': categoria_filtro,
        'busca': busca,
        'categorias': Item.Categoria.choices,
        'total_aprovados': total_aprovados,
        'total_venda': total_venda,
        'total_aluguel': total_aluguel,
    })


def item_detail(request, slug):
    """
    Página rica de detalhes do produto com galeria de fotos, comparativo de preços,
    transparência de defeitos e botão de contato inteligente (WhatsApp/PIX/Telegram).
    """
    seller_config = ConfiguracaoVendedor.get_solo()
    
    # Se o usuário for staff (admin), permite visualizar itens em rascunho
    if request.user.is_staff:
        item = get_object_or_404(Item, slug=slug)
    else:
        item = get_object_or_404(Item, slug=slug, status=Item.Status.APROVADO)

    base_url = request.build_absolute_uri('/')
    wa_data = format_whatsapp_message(item, seller_config, base_url)

    # Cálculo de Economia em relação ao novo
    economia_reais = None
    porcentagem_economia = None
    if item.preco_novo_referencia and item.preco_usado and item.preco_novo_referencia > item.preco_usado:
        economia_reais = item.preco_novo_referencia - item.preco_usado
        porcentagem_economia = round((economia_reais / item.preco_novo_referencia) * 100)

    # Outros itens semelhantes da mesma categoria
    itens_relacionados = Item.objects.filter(
        status=Item.Status.APROVADO,
        categoria=item.categoria
    ).exclude(pk=item.pk)[:4]

    return render(request, 'core/item_detail.html', {
        'item': item,
        'configuracao': seller_config,
        'wa_data': wa_data,
        'economia_reais': economia_reais,
        'porcentagem_economia': porcentagem_economia,
        'itens_relacionados': itens_relacionados,
    })


@staff_member_required
def upload_rapido(request):
    """
    Interface mobile-first de upload rápido de fotos de itens usando a câmera nativa.
    Exclusivo para administradores e equipe do desapego (evita uso indevido de APIs e uploads por visitantes).
    Cria um Item com status 'rascunho' e associa as imagens enviadas.
    """
    if request.method == 'POST':
        imagens = request.FILES.getlist('imagens')
        titulo_provisorio = request.POST.get('titulo_provisorio', '').strip()
        observacoes = request.POST.get('observacoes', '').strip()
        categoria = request.POST.get('categoria', Item.Categoria.OUTROS)
        tipo_anuncio = request.POST.get('tipo_anuncio', Item.TipoAnuncio.VENDA)
        capa_index = request.POST.get('capa_index', '0')

        try:
            capa_index = int(capa_index)
        except ValueError:
            capa_index = 0

        seller_config = ConfiguracaoVendedor.get_solo()
        if not imagens:
            messages.error(request, "Por favor, selecione ou tire pelo menos uma foto do item.")
            return render(request, 'core/upload_rapido.html', {
                'configuracao': seller_config,
                'categorias': Item.Categoria.choices,
                'tipos_anuncio': Item.TipoAnuncio.choices,
            })

        if not titulo_provisorio:
            agora = timezone.localtime(timezone.now()).strftime('%d/%m às %H:%M')
            titulo_provisorio = f"Item em análise ({agora})"

        descricao_sugerida = request.POST.get('descricao_ia', '').strip()

        item = Item.objects.create(
            titulo=titulo_provisorio,
            categoria=categoria,
            tipo_anuncio=tipo_anuncio,
            status=Item.Status.RASCUNHO,
            defeitos_visiveis=observacoes,
            descricao_ia=descricao_sugerida,
            descricao_manual=""
        )

        for i, imagem_file in enumerate(imagens):
            is_principal = (i == capa_index) or (i == 0 and capa_index >= len(imagens))
            ImagemItem.objects.create(
                item=item,
                imagem=imagem_file,
                ordem=i,
                principal=is_principal
            )

        return render(request, 'core/upload_sucesso.html', {
            'item': item,
            'total_fotos': len(imagens)
        })

    seller_config = ConfiguracaoVendedor.get_solo()
    return render(request, 'core/upload_rapido.html', {
        'configuracao': seller_config,
        'categorias': Item.Categoria.choices,
        'tipos_anuncio': Item.TipoAnuncio.choices,
    })


@staff_member_required
def quick_delete_item(request, item_id):
    """
    Endpoint para exclusão rápida de um item via AJAX ou requisição direta no painel admin.
    """
    item = get_object_or_404(Item, pk=item_id)
    titulo = item.titulo

    if request.method in ['POST', 'DELETE']:
        item.delete()
        if request.headers.get('accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({
                'success': True,
                'message': f"Item '{titulo}' excluído com sucesso.",
                'item_id': item_id,
            })
        messages.success(request, f"Item '{titulo}' excluído com sucesso.")
        return redirect('/admin/core/item/')

    return JsonResponse({'error': 'Método não permitido. Use POST para excluir.'}, status=405)

