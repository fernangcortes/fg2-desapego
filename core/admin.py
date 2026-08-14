from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Item, ImagemItem, ConfiguracaoVendedor
from ai_engine.services import AIOrchestrator

# Customização do cabeçalho do Django Admin
admin.site.site_header = "Hub de Desapego Inteligente"
admin.site.site_title = "Admin Hub de Desapego"
admin.site.index_title = "Painel de Gerenciamento de Itens"


class ImagemItemInline(admin.TabularInline):
    model = ImagemItem
    extra = 1
    fields = ('imagem', 'thumbnail_preview', 'legenda', 'ordem', 'principal')
    readonly_fields = ('thumbnail_preview',)

    def thumbnail_preview(self, obj):
        if obj.imagem:
            return format_html(
                '<div style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px;">'
                '<img src="{}" style="width: 75px; height: 75px; object-fit: cover; border-radius: 6px; border: 1px solid #ddd;" />'
                '<button type="button" class="admin-subtle-btn admin-lens-btn" data-image-url="{}" title="Buscar esta foto no Google Lens (abre com a imagem e copia para área de transferência)" style="display: inline-flex; align-items: center; gap: 3px; font-size: 10px; font-weight: 600; color: #0284c7; background: #f0f9ff; padding: 2px 6px; border-radius: 4px; border: 1px solid #bae6fd; cursor: pointer;">'
                '🔍 Google Lens'
                '</button>'
                '</div>',
                obj.imagem.url,
                obj.imagem.url
            )
        return "-"
    thumbnail_preview.short_description = "Prévia & Lens"


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        'thumbnail_preview',
        'titulo',
        'categoria',
        'tipo_anuncio',
        'preco_usado_formatado',
        'preco_novo_formatado',
        'status_badge',
        'botoes_acao',
        'destaque',
        'criado_em',
    )
    list_display_links = ('thumbnail_preview', 'titulo')
    list_filter = ('status', 'tipo_anuncio', 'categoria', 'estado_conservacao', 'destaque', 'criado_em')
    search_fields = ('titulo', 'descricao_ia', 'descricao_manual', 'defeitos_visiveis')
    prepopulated_fields = {'slug': ('titulo',)}
    inlines = [ImagemItemInline]
    readonly_fields = ('criado_em', 'atualizado_em', 'urls_referencia_formatadas')
    list_per_page = 25

    class Media:
        css = {
            'all': (
                'css/admin_subtle_actions.css',
                'css/admin_ai_terminal.css',
            )
        }
        js = (
            'js/admin_ai_terminal.js',
            'js/admin_subtle_actions.js',
        )


    fieldsets = (
        ("Informações Principais", {
            'fields': (
                ('titulo', 'slug'),
                ('categoria', 'tipo_anuncio', 'estado_conservacao'),
                ('status', 'destaque'),
            )
        }),
        ("Precificação (R$)", {
            'fields': (
                ('preco_usado', 'preco_novo_referencia', 'preco_aluguel'),
            ),
            'description': "Defina o valor de venda, referência de novo no mercado e/ou valor de aluguel."
        }),
        ("Descrições e Copywriting", {
            'fields': (
                'descricao_manual',
                'descricao_ia',
                'defeitos_visiveis',
            ),
            'description': "A 'Descrição Manual' tem prioridade de exibição no site. Se vazia, a 'Descrição Sugerida por IA' será usada."
        }),
        ("Inteligência Artificial & Pesquisa de Mercado", {
            'fields': (
                'urls_referencia_formatadas',
                'urls_referencia',
            ),
            'description': "URLs e referências consultadas pela IA."
        }),
        ("Metadados", {
            'classes': ('collapse',),
            'fields': (
                ('criado_em', 'atualizado_em'),
            )
        }),
    )

    actions = ['processar_com_ia', 'processar_com_serpapi_lens', 'aprovar_itens', 'marcar_como_vendidos', 'marcar_como_rascunho']

    def thumbnail_preview(self, obj):
        img = obj.imagem_principal
        if img and img.imagem:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />',
                img.imagem.url
            )
        return format_html('<span style="color: #999; font-size: 11px;">Sem foto</span>')
    thumbnail_preview.short_description = "Foto"

    def preco_usado_formatado(self, obj):
        if obj.preco_usado is not None:
            return f"R$ {obj.preco_usado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return "-"
    preco_usado_formatado.short_description = "Preço Venda"
    preco_usado_formatado.admin_order_field = "preco_usado"

    def preco_novo_formatado(self, obj):
        if obj.preco_novo_referencia is not None:
            return f"R$ {obj.preco_novo_referencia:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return "-"
    preco_novo_formatado.short_description = "Preço Novo Ref."
    preco_novo_formatado.admin_order_field = "preco_novo_referencia"

    def status_badge(self, obj):
        colors = {
            Item.Status.RASCUNHO: ('#fef3c7', '#92400e'),   # amarelo
            Item.Status.APROVADO: ('#dcfce7', '#166534'),   # verde
            Item.Status.VENDIDO: ('#e2e8f0', '#475569'),    # cinza
            Item.Status.ALUGADO: ('#dbeafe', '#1e40af'),    # azul
        }
        bg, text = colors.get(obj.status, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px;">{}</span>',
            bg, text, obj.get_status_display()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def botoes_acao(self, obj):
        process_url = reverse('ai_engine:process_item', args=[obj.pk])
        process_serpapi_url = f"{process_url}?serpapi=1"
        export_url = reverse('marketplace:export_modal', args=[obj.pk])
        delete_url = reverse('core:quick_delete_item', args=[obj.pk])
        return format_html(
            '<div class="admin-subtle-actions" style="display:inline-flex; align-items:center; gap:8px;">'
            '<a href="{}" class="admin-subtle-btn admin-ai-action-btn" data-item-id="{}" data-item-title="{}" title="Processar com IA (Padrão Gratuito)" style="display:inline-flex; width:18px; height:18px; color:#6366f1;">'
            '<svg viewBox="0 0 24 24" style="width:17px; height:17px; min-width:17px; stroke:currentColor; fill:none; stroke-width:1.8;"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/><path d="M5 3v4"/><path d="M19 17v4"/></svg>'
            '</a>'
            '<a href="{}" class="admin-subtle-btn admin-ai-action-btn admin-serpapi-btn" data-item-id="{}" data-item-title="{}" data-serpapi="1" title="Análise Profunda Google Lens (SerpApi)" style="display:inline-flex; width:18px; height:18px; color:#d97706;">'
            '<svg viewBox="0 0 24 24" style="width:17px; height:17px; min-width:17px; stroke:currentColor; fill:none; stroke-width:1.8;"><circle cx="12" cy="12" r="3"/><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/></svg>'
            '</a>'
            '<a href="{}" class="admin-subtle-btn admin-export-action-btn" title="Exportar Anúncio" style="display:inline-flex; width:18px; height:18px;">'
            '<svg viewBox="0 0 24 24" style="width:17px; height:17px; min-width:17px; stroke:currentColor; fill:none; stroke-width:1.8;"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/></svg>'
            '</a>'
            '<button type="button" class="admin-subtle-btn admin-delete-action-btn" '
            'data-item-id="{}" data-item-title="{}" data-delete-url="{}" title="Excluir este item" style="display:inline-flex; align-items:center; background:none; border:none; padding:0; cursor:pointer;">'
            '<svg viewBox="0 0 24 24" style="width:17px; height:17px; min-width:17px; stroke:currentColor; fill:none; stroke-width:1.8;">'
            '<path class="trash-lid" d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
            '<path class="trash-body" d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0v10m4-10v10m4-10v10"/>'
            '</svg>'
            '<span class="delete-confirm-label">Excluir?</span>'
            '</button>'
            '</div>',
            process_url, obj.pk, obj.titulo,
            process_serpapi_url, obj.pk, obj.titulo,
            export_url, obj.pk, obj.titulo, delete_url
        )
    botoes_acao.short_description = "Ações Rápidas"


    def urls_referencia_formatadas(self, obj):
        if not obj.urls_referencia:
            return format_html('<span style="color: #94a3b8; font-style: italic; font-size: 12px;">Nenhuma URL de referência registrada. Execute a pipeline de IA para pesquisar.</span>')

        items_html = []
        for url in obj.urls_referencia:
            if not isinstance(url, str) or not url.startswith("http"):
                continue

            url_lower = url.lower()
            if "mercadolivre.com" in url_lower:
                badge_bg = "#fef08a"
                badge_color = "#854d0e"
                label = "Mercado Livre"
                icon = "🟡"
            elif "amazon.com" in url_lower:
                badge_bg = "#ffedd5"
                badge_color = "#9a3412"
                label = "Amazon Brasil"
                icon = "🟠"
            elif "shopee.com" in url_lower:
                badge_bg = "#fee2e2"
                badge_color = "#991b1b"
                label = "Shopee"
                icon = "🔴"
            elif "aliexpress.com" in url_lower:
                badge_bg = "#ffedd5"
                badge_color = "#c2410c"
                label = "AliExpress"
                icon = "🟧"
            elif "kabum.com" in url_lower:
                badge_bg = "#dbeafe"
                badge_color = "#1e40af"
                label = "KaBuM!"
                icon = "🔵"
            elif "magazineluiza.com" in url_lower or "magalu" in url_lower:
                badge_bg = "#e0e7ff"
                badge_color = "#3730a3"
                label = "Magalu"
                icon = "🟣"
            elif "lens.google.com" in url_lower:
                badge_bg = "#e0f2fe"
                badge_color = "#0369a1"
                label = "Google Lens"
                icon = "🔍"
            elif "google.com" in url_lower:
                badge_bg = "#f1f5f9"
                badge_color = "#334155"
                label = "Google Busca"
                icon = "🔍"
            elif "lojatomate.com" in url_lower or "sennheiser.com" in url_lower or "yamaha.com" in url_lower:
                badge_bg = "#f0fdf4"
                badge_color = "#166534"
                label = "Loja Oficial / Fabricante"
                icon = "🏷️"
            else:
                badge_bg = "#f0fdf4"
                badge_color = "#166534"
                label = "Referência Web / Loja"
                icon = "🌐"

            items_html.append(
                f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">'
                f'<span style="background-color: {badge_bg}; color: {badge_color}; padding: 2px 7px; border-radius: 6px; font-weight: 700; font-size: 11px; white-space: nowrap;">{icon} {label}</span>'
                f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="color: #0284c7; text-decoration: none; font-size: 12px; word-break: break-all;" onmouseover="this.style.textDecoration=\'underline\'" onmouseout="this.style.textDecoration=\'none\'">'
                f'{url} ↗'
                f'</a>'
                f'</div>'
            )

        if not items_html:
            return format_html('<span style="color: #94a3b8; font-style: italic; font-size: 12px;">Nenhuma URL válida registrada.</span>')

        return format_html('<div style="background: #f8fafc; padding: 10px 14px; border-radius: 8px; border: 1px solid #e2e8f0;">{}</div>', format_html("".join(items_html)))
    urls_referencia_formatadas.short_description = "Links de Referência (Clicáveis)"

    @admin.action(description="🤖 Processar selecionados com IA (Padrão Gratuito)")
    def processar_com_ia(self, request, queryset):
        processados = 0
        for item in queryset:
            res = AIOrchestrator.process_item(item.id, use_serpapi=False)
            if res.get('success'):
                processados += 1
        self.message_user(request, f"{processados} item(ns) processado(s) pela pipeline gratuita de IA com sucesso.")

    @admin.action(description="🔍 Processar com Google Lens Profundo (SerpApi - On-Demand)")
    def processar_com_serpapi_lens(self, request, queryset):
        processados = 0
        for item in queryset:
            res = AIOrchestrator.process_item(item.id, use_serpapi=True)
            if res.get('success'):
                processados += 1
        self.message_user(request, f"{processados} item(ns) processado(s) com Google Lens Profundo (SerpApi).")

    @admin.action(description="Aprovar itens selecionados (Publicar no Site)")
    def aprovar_itens(self, request, queryset):
        count = 0
        for item in queryset:
            item.status = Item.Status.APROVADO
            item.save()
            count += 1
        self.message_user(request, f"{count} item(ns) aprovado(s) com sucesso.")

    @admin.action(description="Marcar itens selecionados como Vendidos")
    def marcar_como_vendidos(self, request, queryset):
        count = queryset.update(status=Item.Status.VENDIDO)
        self.message_user(request, f"{count} item(ns) marcado(s) como vendido(s).")

    @admin.action(description="Mover itens selecionados para Rascunho")
    def marcar_como_rascunho(self, request, queryset):
        count = queryset.update(status=Item.Status.RASCUNHO)
        self.message_user(request, f"{count} item(ns) movido(s) para rascunho.")


@admin.register(ConfiguracaoVendedor)
class ConfiguracaoVendedorAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Identificação do Vendedor", {
            'fields': ('nome_vendedor', 'mensagem_boas_vindas')
        }),
        ("Canais de Contato", {
            'fields': (
                ('whatsapp', 'telegram'),
                'email'
            ),
            'description': "Estes dados serão usados para gerar links diretos de WhatsApp e botões de contato."
        }),
        ("Dados Financeiros", {
            'fields': ('chave_pix',),
            'description': "Chave PIX que pode ser exibida aos interessados."
        }),
    )

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
