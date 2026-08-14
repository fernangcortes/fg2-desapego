import re
from django import template
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt

register = template.Library()

# Instância reutilizável do parser Markdown seguro (desabilita HTML cru para evitar XSS e ativa quebras de linha automáticas)
_md_parser = MarkdownIt("commonmark", {"breaks": True, "html": False})


@register.filter(name="render_markdown")
def render_markdown(value: str) -> str:
    """
    Renderiza texto em Markdown (gerado pela IA ou manual) em HTML formatado e seguro.
    Normaliza marcadores de lista unicode (•) e títulos com marcações redundantes.
    """
    if not value or not isinstance(value, str):
        return ""

    text = value

    # 1. Normaliza marcadores de tópicos unicode (•, ●, ▪) para listas Markdown padrão (- )
    text = re.sub(r"(?m)^\s*[•●▪]\s+", "- ", text)

    # 2. Limpa asteriscos redundantes dentro de títulos Markdown (ex: ## **Título** -> ## Título)
    text = re.sub(r"(?m)^(#{1,6}\s+)\*\*(.*?)\*\*", r"\1\2", text)

    # 3. Renderiza Markdown para HTML
    html = _md_parser.render(text)

    return mark_safe(html)


@register.filter(name="strip_markdown")
def strip_markdown(value: str) -> str:
    """
    Remove todos os símbolos e delimitadores Markdown (#, **, *, _, ~~, marcadores de lista),
    retornando texto puro limpo ideal para resumos em cards, tags meta e mensagens.
    """
    if not value or not isinstance(value, str):
        return ""

    text = value

    # Remove blocos de código
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove cabeçalhos Markdown (#, ##, ###, etc.)
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)

    # Transforma links [texto](url) apenas em texto
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove formatações de negrito, itálico e tachado
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    text = re.sub(r"~~(.*?)~~", r"\1", text)

    # Remove marcadores de tópicos e listas do início de linhas
    text = re.sub(r"(?m)^\s*[-*+•●▪]\s+", "", text)
    text = re.sub(r"(?m)^\s*\d+\.\s+", "", text)

    # Remove blockquotes
    text = re.sub(r"(?m)^\s*>\s*", "", text)

    # Normaliza múltiplos espaços e quebras de linha em espaço simples
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()
