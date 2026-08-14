import os
import json
import base64
import logging
import re
from typing import Dict, Any, List, Optional
import requests
from django.conf import settings
from core.models import Item, ImagemItem

logger = logging.getLogger(__name__)


class VisionService:
    """
    Serviço de Visão Computacional (Google Gemini Flash ou Groq Llama 3.2 Vision).
    Analisa fotos para identificar produto, marca, modelo e defeitos visíveis.
    """
    @classmethod
    def analyze_item_images(cls, item: Item) -> Dict[str, Any]:
        api_config = getattr(settings, 'AI_CONFIG', {})
        gemini_key = api_config.get('GEMINI_API_KEY')
        groq_key = api_config.get('GROQ_API_KEY')

        # Coleta imagens
        imagens = item.imagens.all()
        if not imagens.exists():
            return cls._fallback_vision_data(item, "Nenhuma foto fornecida.")

        # Tenta Gemini primeiro se configurado
        if gemini_key:
            try:
                return cls._call_gemini_vision(imagens, gemini_key, item)
            except Exception as e:
                logger.error(f"Erro no Gemini Vision: {e}")

        # Tenta Groq se configurado
        if groq_key:
            try:
                return cls._call_groq_vision(imagens, groq_key, item)
            except Exception as e:
                logger.error(f"Erro no Groq Vision: {e}")

        # Fallback inteligente se nenhuma chave estiver configurada
        return cls._fallback_vision_data(item)

    @classmethod
    def _call_gemini_vision(cls, imagens, api_key: str, item: Item) -> Dict[str, Any]:
        candidate_models = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
        parts = []

        system_instruction = (
            "Você é um perito em avaliação visual de itens usados para venda e desapego. "
            "Analise as fotos com atenção aos mínimos detalhes. "
            "Identifique exatamente o produto, marca, modelo, estado real de conservação e "
            "CRUCIALMENTE: aponte qualquer defeito, arranhão, mancha, oxidação, poeira ou detalhe de uso visível. "
            "Responda ESTRITAMENTE em formato JSON com as chaves: "
            "produto_identificado (string), marca (string), modelo (string), "
            "categoria_sugerida (uma entre: eletronicos, moveis, eletrodomesticos, ferramentas, instrumentos, vestuario, esportes, livros, outros), "
            "estado_conservacao (um entre: novo, excelente, bom, marcas_uso, defeito_reparo), "
            "defeitos_visiveis (string detalhada em português), "
            "acessorios_visiveis (string com cabos, caixas ou manuais identificados)."
        )
        parts.append({"text": system_instruction})
        if item.defeitos_visiveis:
            parts.append({"text": f"Observação informada pelo vendedor: {item.defeitos_visiveis}"})

        # Adiciona até 4 imagens em base64
        for img_obj in imagens[:4]:
            if hasattr(img_obj, 'imagem') and img_obj.imagem and os.path.exists(img_obj.imagem.path):
                with open(img_obj.imagem.path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode('utf-8')
                    mime_type = "image/jpeg" if img_obj.imagem.path.lower().endswith(('.jpg', '.jpeg')) else "image/png"
                    parts.append({
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": b64_data
                        }
                    })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        last_error = None
        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                resp = requests.post(url, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                content_text = data['candidates'][0]['content']['parts'][0]['text']
                return json.loads(content_text)
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        raise Exception("Nenhum modelo Gemini retornou resposta válida.")

    @classmethod
    def _call_groq_vision(cls, imagens, api_key: str, item: Item) -> Dict[str, Any]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        content_parts = []
        content_parts.append({
            "type": "text",
            "text": (
                "Identifique o produto nas fotos e liste defeitos visíveis. "
                "Retorne estritamente um JSON com: produto_identificado, marca, modelo, "
                "categoria_sugerida, estado_conservacao, defeitos_visiveis, acessorios_visiveis."
            )
        })

        for img_obj in imagens[:2]:
            if os.path.exists(img_obj.imagem.path):
                with open(img_obj.imagem.path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode('utf-8')
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}
                    })

        payload = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [{"role": "user", "content": content_parts}],
            "response_format": {"type": "json_object"}
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        res_json = resp.json()
        return json.loads(res_json['choices'][0]['message']['content'])

    @classmethod
    def _fallback_vision_data(cls, item: Item, motivo: str = "") -> Dict[str, Any]:
        nome = item.titulo if not item.titulo.startswith("Item em análise") else "Item Avaliado"
        return {
            "produto_identificado": nome,
            "marca": "Genérica / Não identificada",
            "modelo": "Padrão",
            "categoria_sugerida": item.categoria or "outros",
            "estado_conservacao": item.estado_conservacao or "bom",
            "defeitos_visiveis": item.defeitos_visiveis or "Leves marcas naturais de manuseio e uso cotidiano.",
            "acessorios_visiveis": "Acessórios e itens visíveis conforme as fotos anexadas."
        }


class MarketSearchService:
    """
    Serviço de Pesquisa de Mercado (Tavily API / Serper API).
    Busca o preço médio do produto NOVO (Amazon/ML) e USADO (OLX/Enjoei) e coleta URLs.
    """
    @classmethod
    def search_market_prices(cls, produto_nome: str) -> Dict[str, Any]:
        api_config = getattr(settings, 'AI_CONFIG', {})
        tavily_key = api_config.get('TAVILY_API_KEY')
        serper_key = api_config.get('SERPER_API_KEY')

        if tavily_key:
            try:
                return cls._call_tavily(produto_nome, tavily_key)
            except Exception as e:
                logger.error(f"Erro na API Tavily: {e}")

        if serper_key:
            try:
                return cls._call_serper(produto_nome, serper_key)
            except Exception as e:
                logger.error(f"Erro na API Serper: {e}")

        # Fallback de busca de mercado
        return cls._fallback_market_data(produto_nome)

    @classmethod
    def _call_tavily(cls, query: str, api_key: str) -> Dict[str, Any]:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": f"{query} preco mercado livre amazon brasil",
            "search_depth": "basic",
            "max_results": 5
        }
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        urls = [r.get('url') for r in data.get('results', []) if r.get('url')]
        snippets = " ".join([r.get('content', '') for r in data.get('results', [])])
        precos = cls._extract_prices_from_text(snippets)

        preco_novo = precos.get('preco_novo')
        preco_usado = precos.get('preco_usado')

        return {
            "preco_novo_estimado": preco_novo,
            "preco_usado_medio": preco_usado,
            "urls_referencia": urls[:5]
        }

    @classmethod
    def _call_serper(cls, query: str, api_key: str) -> Dict[str, Any]:
        url = "https://google.serper.dev/search"
        payload = {
            "q": f"{query} preço brasil",
            "gl": "br",
            "hl": "pt-br",
            "num": 5
        }
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        urls = [r.get('link') for r in data.get('organic', []) if r.get('link')]
        snippets = " ".join([r.get('snippet', '') for r in data.get('organic', [])])
        precos = cls._extract_prices_from_text(snippets)

        return {
            "preco_novo_estimado": precos.get('preco_novo'),
            "preco_usado_medio": precos.get('preco_usado'),
            "urls_referencia": urls[:5]
        }

    @classmethod
    def _extract_prices_from_text(cls, text: str) -> Dict[str, Optional[float]]:
        # Procura padrões como R$ 150,00 ou R$ 1.250,90
        padrao = r'R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)'
        matches = re.findall(padrao, text)
        valores = []
        for m in matches:
            try:
                v = float(m.replace('.', '').replace(',', '.'))
                if 10.0 <= v <= 100000.0:
                    valores.append(v)
            except ValueError:
                continue

        if not valores:
            return {"preco_novo": None, "preco_usado": None}

        valores.sort()
        preco_usado = round(valores[len(valores)//3], 2) if len(valores) > 1 else valores[0]
        preco_novo = round(valores[-1], 2)
        return {"preco_novo": preco_novo, "preco_usado": preco_usado}

    @classmethod
    def _fallback_market_data(cls, produto_nome: str) -> Dict[str, Any]:
        return {
            "preco_novo_estimado": None,
            "preco_usado_medio": None,
            "urls_referencia": [
                f"https://lista.mercadolivre.com.br/{requests.utils.quote(produto_nome)}",
                f"https://www.google.com/search?q={requests.utils.quote(produto_nome)}+preco"
            ]
        }


class CopywritingService:
    """
    Serviço de Copywriting (DeepSeek API ou fallback).
    Gera Título Otimizado, Descrição Honesta e Sugestão de Preços Justos.
    """
    @classmethod
    def generate_listing_copy(
        cls,
        vision_data: Dict[str, Any],
        market_data: Dict[str, Any],
        observacoes_vendedor: str = ""
    ) -> Dict[str, Any]:
        api_config = getattr(settings, 'AI_CONFIG', {})
        deepseek_key = api_config.get('DEEPSEEK_API_KEY')
        gemini_key = api_config.get('GEMINI_API_KEY')

        if deepseek_key:
            try:
                return cls._call_deepseek_copywriting(vision_data, market_data, observacoes_vendedor, deepseek_key)
            except Exception as e:
                logger.error(f"Erro no DeepSeek Copywriting: {e}")

        if gemini_key:
            try:
                return cls._call_gemini_copywriting(vision_data, market_data, observacoes_vendedor, gemini_key)
            except Exception as e:
                logger.error(f"Erro no Gemini Copywriting: {e}")

        # Fallback de copywriting estruturado e honesto
        return cls._fallback_copywriting(vision_data, market_data, observacoes_vendedor)

    @classmethod
    def _call_deepseek_copywriting(
        cls,
        vision_data: Dict[str, Any],
        market_data: Dict[str, Any],
        observacoes: str,
        api_key: str
    ) -> Dict[str, Any]:
        url = "https://api.deepseek.com/chat/completions"
        system_prompt = (
            "Você é um redator profissional especializado em anúncios de desapego e marketplace no Brasil (OLX, Mercado Livre, Facebook). "
            "Sua marca registrada é a TRANSPARÊNCIA TOTAL: o anúncio deve ser atraente e claro, porém 100% honesto, "
            "destacando claramente qualquer defeito ou marca de uso identificada para gerar confiança instantânea.\n"
            "Retorne a resposta estritamente em JSON com o seguinte formato:\n"
            "{\n"
            '  "titulo": "Título objetivo com marca, modelo e atributo principal (max 70 chars)",\n'
            '  "descricao": "Descrição completa, organizada em tópicos: Visão Geral, Estado Real / Detalhes Visíveis, O que Acompanha e Condições de Retirada/Envio",\n'
            '  "preco_usado": 0.00,\n'
            '  "preco_novo": 0.00,\n'
            '  "preco_aluguel": 0.00\n'
            "}"
        )

        user_content = json.dumps({
            "dados_visuais": vision_data,
            "pesquisa_mercado": market_data,
            "observacoes_adicionais_vendedor": observacoes
        }, ensure_ascii=False)

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"}
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content']
        return json.loads(content)

    @classmethod
    def _call_gemini_copywriting(
        cls,
        vision_data: Dict[str, Any],
        market_data: Dict[str, Any],
        observacoes: str,
        api_key: str
    ) -> Dict[str, Any]:
        candidate_models = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
        prompt = (
            "Crie um anúncio honesto e atraente para venda de item usado no Brasil. "
            f"Dados: Visão: {json.dumps(vision_data, ensure_ascii=False)}, "
            f"Mercado: {json.dumps(market_data, ensure_ascii=False)}, "
            f"Obs Vendedor: {observacoes}. "
            "Retorne estritamente JSON com: titulo, descricao, preco_usado (float), preco_novo (float), preco_aluguel (float)."
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        last_error = None
        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                resp = requests.post(url, json=payload, timeout=30)
                resp.raise_for_status()
                text = resp.json()['candidates'][0]['content']['parts'][0]['text']
                return json.loads(text)
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        raise Exception("Nenhum modelo Gemini retornou resposta válida.")

    @classmethod
    def _fallback_copywriting(
        cls,
        vision_data: Dict[str, Any],
        market_data: Dict[str, Any],
        observacoes: str
    ) -> Dict[str, Any]:
        prod = vision_data.get('produto_identificado', 'Produto em Desapego')
        marca = vision_data.get('marca', '')
        defeitos = vision_data.get('defeitos_visiveis', 'Em bom estado geral com marcas leves de uso.')
        acessorios = vision_data.get('acessorios_visiveis', 'Itens exibidos nas fotos.')

        preco_novo = market_data.get('preco_novo_estimado') or 250.00
        preco_usado = market_data.get('preco_usado_medio') or round(preco_novo * 0.6, 2)
        preco_aluguel = round(preco_usado * 0.15, 2)

        descricao = (
            f"📦 **{prod}**\n\n"
            f"🔹 **Marca/Modelo:** {marca}\n"
            f"🔹 **Estado de Conservação:** {vision_data.get('estado_conservacao', 'Bom estado').capitalize()}\n\n"
            f"🔍 **Detalhes e Estado Real (Transparência Total):**\n"
            f"{defeitos}\n\n"
            f"🎁 **Itens Inclusos:**\n"
            f"{acessorios}\n\n"
            f"{'📝 Observação do Vendedor: ' + observacoes if observacoes else ''}\n\n"
            f"💬 *Fique à vontade para tirar dúvidas e negociar através dos nossos canais de contato!*"
        )

        return {
            "titulo": f"{prod} - {marca}".strip(" -"),
            "descricao": descricao,
            "preco_usado": preco_usado,
            "preco_novo": preco_novo,
            "preco_aluguel": preco_aluguel
        }


class NotificationService:
    """
    Serviço de Notificação para o Vendedor (Telegram Bot / E-mail / Log).
    """
    @classmethod
    def notify_draft_ready(cls, item: Item) -> bool:
        api_config = getattr(settings, 'AI_CONFIG', {})
        bot_token = api_config.get('TELEGRAM_BOT_TOKEN')
        chat_id = api_config.get('TELEGRAM_CHAT_ID')

        if not bot_token or not chat_id:
            logger.info(f"[NOTIFICAÇÃO INTERNA] Item '{item.titulo}' (ID {item.id}) pronto para aprovação no Admin.")
            return True

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            preco_txt = f"R$ {item.preco_usado:,.2f}" if item.preco_usado else "Não definido"
            texto = (
                f"✨ *Novo Desapego Processado pela IA!*\n\n"
                f"📦 *Item:* {item.titulo}\n"
                f"🏷️ *Categoria:* {item.get_categoria_display()}\n"
                f"💰 *Preço Sugerido:* {preco_txt}\n\n"
                f"🔍 *Defeitos detectados:* {item.defeitos_visiveis[:120] if item.defeitos_visiveis else 'Nenhum'}\n\n"
                f"Acesse o painel para aprovar e publicar."
            )
            resp = requests.post(url, json={
                "chat_id": chat_id,
                "text": texto,
                "parse_mode": "Markdown"
            }, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar notificação no Telegram: {e}")
            return False


class AIOrchestrator:
    """
    Orquestrador da Chain of Thought de IA:
    1. Visão -> 2. Pesquisa de Mercado -> 3. Copywriting -> 4. Notificação
    """
    @classmethod
    def process_item(cls, item_id: int) -> Dict[str, Any]:
        try:
            item = Item.objects.get(pk=item_id)
        except Item.DoesNotExist:
            return {"success": False, "error": f"Item {item_id} não encontrado."}

        logger.info(f"Iniciando pipeline de IA para o Item ID {item_id}: {item.titulo}")

        # Passo 1: Visão Computacional
        vision_result = VisionService.analyze_item_images(item)

        # Passo 2: Pesquisa de Mercado
        produto_identificado = vision_result.get('produto_identificado') or item.titulo
        market_result = MarketSearchService.search_market_prices(produto_identificado)

        # Passo 3: Copywriting
        copy_result = CopywritingService.generate_listing_copy(
            vision_data=vision_result,
            market_data=market_result,
            observacoes_vendedor=item.defeitos_visiveis or ""
        )

        # Atualização do Modelo Item
        if copy_result.get('titulo'):
            item.titulo = copy_result['titulo']

        if copy_result.get('descricao'):
            item.descricao_ia = copy_result['descricao']

        if copy_result.get('preco_usado'):
            item.preco_usado = copy_result['preco_usado']

        if copy_result.get('preco_novo'):
            item.preco_novo_referencia = copy_result['preco_novo']

        if copy_result.get('preco_aluguel'):
            item.preco_aluguel = copy_result['preco_aluguel']

        if vision_result.get('categoria_sugerida') in [c[0] for c in Item.Categoria.choices]:
            item.categoria = vision_result['categoria_sugerida']

        if vision_result.get('estado_conservacao') in [e[0] for e in Item.EstadoConservacao.choices]:
            item.estado_conservacao = vision_result['estado_conservacao']

        if vision_result.get('defeitos_visiveis'):
            item.defeitos_visiveis = vision_result['defeitos_visiveis']

        if market_result.get('urls_referencia'):
            item.urls_referencia = market_result['urls_referencia']

        # Salva o item
        item.save()

        # Passo 4: Notificação
        NotificationService.notify_draft_ready(item)

        return {
            "success": True,
            "item_id": item.id,
            "titulo": item.titulo,
            "preco_usado": str(item.preco_usado),
            "categoria": item.categoria
        }
