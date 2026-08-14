import re
import urllib.parse
from core.models import Item, ConfiguracaoVendedor


def get_formatted_price(price):
    if price is None:
        return "A combinar"
    return f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def clean_markdown_for_marketplace(text: str) -> str:
    """
    Remove marcadores técnicos de Markdown (#, **, *, _, ~~) preservando
    a legibilidade, espaçamento de parágrafos e tópicos com bullet (•).
    """
    if not text:
        return ""
    # Remove imagens Markdown ![...](...) e tags HTML <img>
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"<img[^>]*>", "", text)
    # Remove cabeçalhos Markdown (#, ##, etc.)
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    # Remove formatações de negrito, itálico e tachado
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    text = re.sub(r"~~(.*?)~~", r"\1", text)
    # Normaliza marcadores de tópicos para bullet limpo
    text = re.sub(r"(?m)^\s*[-*+]\s+", "• ", text)
    text = re.sub(r"(?m)^\s*[●▪]\s+", "• ", text)
    # Limpa excesso de quebras de linha
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()



def format_for_olx(item: Item, base_url: str = "") -> str:
    """
    Formatação de texto puro otimizada para OLX (sem markdown, tópicos limpos e legíveis).
    """
    preco = get_formatted_price(item.preco_usado)
    estado = item.get_estado_conservacao_display()
    descricao_limpa = clean_markdown_for_marketplace(item.descricao_efetiva)

    texto = (
        f"{item.titulo}\n\n"
        f"💰 VALOR: {preco}\n"
        f"📌 ESTADO: {estado}\n"
        f"🏷️ CATEGORIA: {item.get_categoria_display()}\n\n"
        f"--- DESCRIÇÃO DO PRODUTO ---\n"
        f"{descricao_limpa}\n\n"
    )

    if item.defeitos_visiveis:
        texto += (
            f"🔍 DETALHES / MARCAS DE USO (TRANSPARÊNCIA TOTAL):\n"
            f"{item.defeitos_visiveis}\n\n"
        )

    if item.preco_aluguel and item.tipo_anuncio in [Item.TipoAnuncio.ALUGUEL, Item.TipoAnuncio.AMBOS]:
        texto += f"🔄 DISPONÍVEL TAMBÉM PARA ALUGUEL: {get_formatted_price(item.preco_aluguel)}/período\n\n"

    texto += (
        f"✅ Item testado e revisado.\n"
        f"📦 Retirada em mãos a combinar ou envio.\n"
    )

    if base_url:
        item_link = f"{base_url.rstrip('/')}/item/{item.slug}/"
        texto += f"🔗 Veja fotos em alta resolução e mais detalhes em: {item_link}\n"

    return texto.strip()


def format_for_mercadolivre(item: Item, base_url: str = "") -> str:
    """
    Formatação adaptada para descrição de Mercado Livre.
    """
    preco = get_formatted_price(item.preco_usado)
    estado = item.get_estado_conservacao_display()
    descricao = clean_markdown_for_marketplace(item.descricao_efetiva)

    texto = (
        f"=========================================\n"
        f"{item.titulo.upper()}\n"
        f"=========================================\n\n"
        f"• Condição: {estado}\n"
        f"• Preço: {preco}\n"
        f"• Categoria: {item.get_categoria_display()}\n\n"
        f"--- SOBRE O PRODUTO ---\n"
        f"{descricao}\n\n"
    )

    if item.defeitos_visiveis:
        texto += (
            f"--- ESTADO REAL E DETALHES DE USO ---\n"
            f"Prezamos por 100% de honestidade na venda:\n"
            f"{item.defeitos_visiveis}\n\n"
        )

    texto += (
        f"--- INFORMAÇÕES IMPORTANTES ---\n"
        f"✔ Todas as fotos do anúncio são reais do produto à venda.\n"
        f"✔ Envio rápido ou retirada conforme combinado.\n"
        f"✔ Dúvidas? Utilize o campo de perguntas!"
    )

    return texto.strip()


def format_for_facebook(item: Item, base_url: str = "") -> str:
    """
    Formatação curta e direta para Facebook Marketplace e grupos de desapego.
    """
    preco = get_formatted_price(item.preco_usado)
    estado = item.get_estado_conservacao_display()

    descricao_limpa = clean_markdown_for_marketplace(item.descricao_efetiva)
    if len(descricao_limpa) > 900:
        descricao_exibida = f"{descricao_limpa[:850]}..."
    else:
        descricao_exibida = descricao_limpa

    texto = (
        f"🔥 DESAPEGO: {item.titulo}\n\n"
        f"💲 Valor: {preco}\n"
        f"✨ Estado: {estado}\n\n"
        f"📝 Descrição & Especificações:\n"
        f"{descricao_exibida}\n\n"
    )


    if item.defeitos_visiveis:
        texto += f"🔍 Observação: {item.defeitos_visiveis}\n\n"

    if base_url:
        item_link = f"{base_url.rstrip('/')}/item/{item.slug}/"
        texto += f"👉 Mais fotos e informações no site: {item_link}\n\n"

    texto += "💬 Interessados chamar no chat ou WhatsApp!"
    return texto.strip()


def format_whatsapp_message(item: Item, seller_config: ConfiguracaoVendedor, base_url: str = "") -> dict:
    """
    Gera o texto e link oficial de cotação/interesse para o WhatsApp do vendedor.
    Formato solicitado:
    'Olá, vi seu anúncio no site e tenho interesse no [Produto] pelo valor de [Preço]. Segue link: [Link]'
    """
    preco = get_formatted_price(item.preco_usado)
    item_link = f"{base_url.rstrip('/')}/item/{item.slug}/" if base_url else f"/item/{item.slug}/"

    mensagem = (
        f"Olá, vi seu anúncio no site e tenho interesse no {item.titulo} pelo valor de {preco}. "
        f"Segue link: {item_link}"
    )

    phone = ''.join(filter(str.isdigit, seller_config.whatsapp or ''))
    encoded_text = urllib.parse.quote(mensagem)
    whatsapp_url = f"https://wa.me/{phone}?text={encoded_text}" if phone else f"https://wa.me/?text={encoded_text}"

    return {
        "mensagem": mensagem,
        "whatsapp_url": whatsapp_url,
        "telefone": phone
    }
