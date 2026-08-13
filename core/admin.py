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
                '<img src="{}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 6px; border: 1px solid #ddd;" />',
                obj.imagem.url
            )
        return "-"
    thumbnail_preview.short_description = "Prévia"


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

    actions = ['processar_com_ia', 'aprovar_itens', 'marcar_como_vendidos', 'marcar_como_rascunho']

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
        export_url = reverse('marketplace:export_modal', args=[obj.pk])
        return format_html(
            '<div style="display: flex; gap: 4px; align-items: center;">'
            '<a href="{}" style="background-color: #f3e8ff; color: #6b21a8; padding: 3px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; text-decoration: none; border: 1px solid #d8b4fe;" title="Executar orquestrador de IA">'
            '✨ IA'
            '</a>'
            '<a href="{}" style="background-color: #f0fdf4; color: #15803d; padding: 3px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; text-decoration: none; border: 1px solid #bbf7d0;" title="Copiar textos para OLX/ML/Facebook">'
            '📋 Exportar'
            '</a>'
            '</div>',
            process_url, export_url
        )
    botoes_acao.short_description = "Ações Rápidas"

    def urls_referencia_formatadas(self, obj):
        if not obj.urls_referencia:
            return "Nenhuma URL de referência registrada."
        links = []
        for url in obj.urls_referencia:
            links.append(f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a></li>')
        return format_html('<ul style="margin: 0; padding-left: 18px;">{}</ul>', format_html("".join(links)))
    urls_referencia_formatadas.short_description = "Links de Referência (Clicáveis)"

    @admin.action(description="🤖 Processar selecionados com IA (Visão + Mercado + Copy)")
    def processar_com_ia(self, request, queryset):
        processados = 0
        for item in queryset:
            res = AIOrchestrator.process_item(item.id)
            if res.get('success'):
                processados += 1
        self.message_user(request, f"{processados} item(ns) processado(s) pela pipeline de IA com sucesso.")

    @admin.action(description="Aprovar itens selecionados (Publicar no Site)")
    def aprovar_itens(self, request, queryset):
        count = queryset.update(status=Item.Status.APROVADO)
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
