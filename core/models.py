import uuid
from django.db import models
from django.utils.text import slugify


class ConfiguracaoVendedor(models.Model):
    """
    Configurações gerais de contato e dados do vendedor (Singleton).
    """
    nome_vendedor = models.CharField(
        max_length=150,
        default="Casal Vendedor",
        verbose_name="Nome do Vendedor / Casal"
    )
    whatsapp = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="WhatsApp",
        help_text="Apenas números com DDI e DDD (ex: 5511999999999)"
    )
    telegram = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Telegram",
        help_text="Nome de usuário ou link (ex: @usuario ou t.me/usuario)"
    )
    email = models.EmailField(
        blank=True,
        verbose_name="E-mail de Contato"
    )
    chave_pix = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Chave PIX",
        help_text="Chave PIX para pagamentos diretos"
    )
    mensagem_boas_vindas = models.TextField(
        blank=True,
        default="Olá! Seja bem-vindo à nossa página de desapegos. Todos os itens foram bem cuidados.",
        verbose_name="Mensagem de Boas-Vindas"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do Vendedor"
        verbose_name_plural = "Configurações do Vendedor"

    def __str__(self):
        return f"Configurações: {self.nome_vendedor}"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class Item(models.Model):
    """
    Modelo principal para cada item anunciado no hub de desapego.
    """
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        APROVADO = "aprovado", "Aprovado"
        VENDIDO = "vendido", "Vendido"
        ALUGADO = "alugado", "Alugado"

    class TipoAnuncio(models.TextChoices):
        VENDA = "venda", "Venda"
        ALUGUEL = "aluguel", "Aluguel"
        AMBOS = "ambos", "Venda e Aluguel"

    class EstadoConservacao(models.TextChoices):
        NOVO = "novo", "Novo / Lacrado"
        EXCELENTE = "excelente", "Excelente estado (pouco uso)"
        BOM = "bom", "Bom estado (marcas leves de uso)"
        MARCAS_USO = "marcas_uso", "Marcas de uso visíveis"
        DEFEITO_REPARO = "defeito_reparo", "Com avarias / Para reparo"

    class Categoria(models.TextChoices):
        ELETRONICOS = "eletronicos", "Eletrônicos e Informática"
        MOVEIS = "moveis", "Móveis e Decoração"
        ELETRODOMESTICOS = "eletrodomesticos", "Eletrodomésticos"
        FERRAMENTAS = "ferramentas", "Ferramentas e Casa"
        INSTRUMENTOS = "instrumentos", "Instrumentos Musicais"
        VESTUARIO = "vestuario", "Roupas e Acessórios"
        ESPORTES = "esportes", "Esportes e Lazer"
        LIVROS = "livros", "Livros e Colecionáveis"
        OUTROS = "outros", "Outros"

    titulo = models.CharField(
        max_length=255,
        verbose_name="Título do Item"
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        verbose_name="Slug (URL amigável)"
    )
    descricao_ia = models.TextField(
        blank=True,
        verbose_name="Descrição Sugerida por IA",
        help_text="Descrição gerada automaticamente pela pipeline de IA"
    )
    descricao_manual = models.TextField(
        blank=True,
        verbose_name="Descrição Final / Observações do Vendedor",
        help_text="Texto personalizado ou revisado que será exibido aos compradores"
    )
    preco_novo_referencia = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço Novo de Referência (R$)",
        help_text="Preço de mercado do produto novo para comparação"
    )
    preco_usado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço de Venda (R$)",
        help_text="Preço pedido para venda do item usado"
    )
    preco_aluguel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço de Aluguel (R$)",
        help_text="Valor sugerido caso seja disponibilizado para aluguel"
    )
    tipo_anuncio = models.CharField(
        max_length=20,
        choices=TipoAnuncio.choices,
        default=TipoAnuncio.VENDA,
        verbose_name="Tipo de Anúncio"
    )
    estado_conservacao = models.CharField(
        max_length=30,
        choices=EstadoConservacao.choices,
        default=EstadoConservacao.BOM,
        verbose_name="Estado de Conservação"
    )
    categoria = models.CharField(
        max_length=50,
        choices=Categoria.choices,
        default=Categoria.OUTROS,
        verbose_name="Categoria"
    )
    defeitos_visiveis = models.TextField(
        blank=True,
        verbose_name="Defeitos ou Marcas Visíveis",
        help_text="Defeitos identificados pela visão computacional ou anotados manualmente"
    )
    urls_referencia = models.JSONField(
        default=list,
        blank=True,
        verbose_name="URLs de Referência de Mercado",
        help_text="Links de pesquisas de preço (Amazon, Mercado Livre, OLX, etc.)"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
        verbose_name="Status do Item",
        db_index=True
    )
    destaque = models.BooleanField(
        default=False,
        verbose_name="Item em Destaque?"
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Item"
        verbose_name_plural = "Itens"
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.titulo} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.titulo) or "item"
            unique_slug = base_slug
            counter = 1
            while Item.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    @property
    def descricao_efetiva(self):
        """Retorna a descrição manual se preenchida, caso contrário a descrição gerada por IA."""
        return self.descricao_manual.strip() if self.descricao_manual else self.descricao_ia.strip()

    @property
    def imagem_principal(self):
        """Retorna a imagem principal marcada ou a primeira cadastrada."""
        principal = self.imagens.filter(principal=True).first()
        if principal:
            return principal
        return self.imagens.first()


class ImagemItem(models.Model):
    """
    Imagens associadas a cada Item (permite 1..N fotos por item).
    """
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="imagens",
        verbose_name="Item"
    )
    imagem = models.ImageField(
        upload_to="itens/%Y/%m/",
        verbose_name="Arquivo de Imagem"
    )
    legenda = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Legenda / Observação da Foto"
    )
    ordem = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordem de Exibição"
    )
    principal = models.BooleanField(
        default=False,
        verbose_name="Imagem Principal"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Imagem do Item"
        verbose_name_plural = "Imagens do Item"
        ordering = ['ordem', 'id']

    def __str__(self):
        return f"Imagem #{self.id} de {self.item.titulo}"
