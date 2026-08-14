import os
import json
import base64
import logging
import re
import urllib.parse
from typing import Dict, Any, List, Optional
import requests
from django.conf import settings
from django.utils.text import slugify
from core.models import Item, ImagemItem

logger = logging.getLogger(__name__)


class VisionService:
    """
    Serviço de Visão Computacional (Google Gemini Flash ou Groq Llama 3.2 Vision).
    Analisa fotos para identificar produto, marca, modelo exato, defeitos visíveis e acessórios.
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
            "Você é um perito em avaliação visual e técnica de itens usados para venda e desapego no Brasil. "
            "Analise as fotos com extrema atenção aos detalhes visuais, inscrições de texto, logotipos, modelo e serigrafias no produto.\n"
            "Identifique com precisão:\n"
            "1. Produto identificado completo com tipo e função principal\n"
            "2. Marca exata do fabricante\n"
            "3. Modelo exato (ex: HD 400S, C40, WH-1000XM4, iPhone 13 128GB, etc.)\n"
            "4. Categoria mais adequada\n"
            "5. Estado real de conservação\n"
            "6. CRUCIALMENTE: aponte qualquer defeito, arranhão, mancha, oxidação, poeira ou desgaste de almofadas/cabos visível.\n"
            "7. Acessórios visíveis (cabos, conectores, caixa, manual, capa, adaptadores).\n"
            "8. Especificações perceptíveis visualmente (ex: conector P2 3.5mm destacável, voltagem 110V/220V/Bivolt, tipo de almofada over-ear, controles no cabo).\n\n"
            "Responda ESTRITAMENTE em formato JSON com as chaves:\n"
            "{\n"
            '  "produto_identificado": "string",\n'
            '  "marca": "string",\n'
            '  "modelo": "string",\n'
            '  "categoria_sugerida": "uma entre: eletronicos, moveis, eletrodomesticos, ferramentas, instrumentos, vestuario, esportes, livros, outros",\n'
            '  "estado_conservacao": "um entre: novo, excelente, bom, marcas_uso, defeito_reparo",\n'
            '  "defeitos_visiveis": "string detalhada em português",\n'
            '  "acessorios_visiveis": "string detalhada dos acessórios identificados",\n'
            '  "especificacoes_visiveis": "string com especificações técnicas visíveis"\n'
            "}"
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
                "Identifique com precisão o produto nas fotos, marca e modelo exato, liste defeitos visíveis e acessórios. "
                "Retorne estritamente um JSON com: produto_identificado, marca, modelo, "
                "categoria_sugerida, estado_conservacao, defeitos_visiveis, acessorios_visiveis, especificacoes_visiveis."
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
            "acessorios_visiveis": "Acessórios e itens visíveis conforme as fotos anexadas.",
            "especificacoes_visiveis": "Conforme exibido nas imagens."
        }


class MarketSearchService:
    """
    Serviço de Pesquisa de Mercado e Ficha Técnica (Tavily API / Serper API).
    Busca o preço médio do produto NOVO e USADO no Brasil, especificações técnicas e links específicos.
    """
    @classmethod
    def build_search_query(cls, vision_data: Dict[str, Any], fallback_title: str = "") -> str:
        """
        Gera uma query precisa e otimizada unindo Marca, Modelo e Tipo de Produto,
        evitando termos genéricos ou redundâncias.
        """
        marca = (vision_data.get('marca') or '').strip()
        modelo = (vision_data.get('modelo') or '').strip()
        produto = (vision_data.get('produto_identificado') or '').strip()

        generic_placeholders = {
            'generica', 'genérica', 'generica / nao identificada', 'genérica / não identificada',
            'padrao', 'padrão', 'item avaliado', 'item em análise', 'outros', 'desconhecido', 'desconhecida'
        }

        marca_clean = "" if marca.lower() in generic_placeholders else marca
        modelo_clean = "" if modelo.lower() in generic_placeholders else modelo

        parts = []
        if marca_clean:
            parts.append(marca_clean)
        if modelo_clean and modelo_clean.lower() not in [p.lower() for p in parts]:
            parts.append(modelo_clean)

        if produto:
            produto_words = []
            for word in produto.split():
                w_lower = word.lower()
                if (marca_clean and w_lower in marca_clean.lower()) or (modelo_clean and w_lower in modelo_clean.lower()):
                    continue
                if w_lower in generic_placeholders:
                    continue
                produto_words.append(word)
            if produto_words:
                parts.append(" ".join(produto_words))

        query = " ".join(parts).strip()
        if not query or len(query) < 3:
            if fallback_title and not fallback_title.lower().startswith("item em análise"):
                query = fallback_title.strip()
            else:
                query = produto if produto else "Produto Desapego"

        return query

    @classmethod
    def search_market_prices(cls, produto_query: str) -> Dict[str, Any]:
        api_config = getattr(settings, 'AI_CONFIG', {})
        tavily_key = api_config.get('TAVILY_API_KEY')
        serper_key = api_config.get('SERPER_API_KEY')

        if tavily_key:
            try:
                return cls._call_tavily(produto_query, tavily_key)
            except Exception as e:
                logger.error(f"Erro na API Tavily: {e}")

        if serper_key:
            try:
                return cls._call_serper(produto_query, serper_key)
            except Exception as e:
                logger.error(f"Erro na API Serper: {e}")

        # Fallback de busca de mercado
        return cls._fallback_market_data(produto_query)

    @classmethod
    def _call_tavily(cls, query: str, api_key: str) -> Dict[str, Any]:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": f"{query} preco ficha tecnica mercado livre amazon brasil",
            "search_depth": "advanced",
            "max_results": 8
        }
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        raw_urls = [r.get('url') for r in data.get('results', []) if r.get('url')]
        snippets_list = [r.get('content', '') for r in data.get('results', []) if r.get('content')]
        all_snippets = " ".join(snippets_list)

        precos = cls._extract_prices_from_text(all_snippets)
        filtered_urls = cls._filter_and_rank_urls(raw_urls, query)

        return {
            "preco_novo_estimado": precos.get('preco_novo'),
            "preco_usado_medio": precos.get('preco_usado'),
            "urls_referencia": filtered_urls,
            "snippets_pesquisa": all_snippets[:2000]
        }

    @classmethod
    def _call_serper(cls, query: str, api_key: str) -> Dict[str, Any]:
        url = "https://google.serper.dev/search"
        payload = {
            "q": f"{query} preço especificações mercado livre amazon brasil",
            "gl": "br",
            "hl": "pt-br",
            "num": 8
        }
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        raw_urls = [r.get('link') for r in data.get('organic', []) if r.get('link')]
        snippets_list = [r.get('snippet', '') for r in data.get('organic', []) if r.get('snippet')]
        all_snippets = " ".join(snippets_list)

        precos = cls._extract_prices_from_text(all_snippets)
        filtered_urls = cls._filter_and_rank_urls(raw_urls, query)

        return {
            "preco_novo_estimado": precos.get('preco_novo'),
            "preco_usado_medio": precos.get('preco_usado'),
            "urls_referencia": filtered_urls,
            "snippets_pesquisa": all_snippets[:2000]
        }

    @classmethod
    def _filter_and_rank_urls(cls, raw_urls: List[str], query: str) -> List[str]:
        """
        Filtra URLs genéricas, de blog, listas de mais vendidos e nós vazios,
        priorizando páginas de produto diretas e adicionando links de busca específicos do produto.
        """
        # Padrões indesejados (blogs, listas de mais vendidos, nós de categoria genéricos)
        junk_patterns = [
            r'/blog/',
            r'/artigos/',
            r'/noticias/',
            r'/materias/',
            r'/guias/',
            r'/listas/',
            r'/gp/bestsellers/',
            r'/bestsellers/',
            r'/best-sellers/',
            r'/zgbs/',
            r'/b\?ie=UTF8',
            r'/node=\d+',
            r'/departamento/',
            r'/categoria/',
            r'youtube\.com',
            r'techtudo\.com\.br/listas/',
            r'zoom\.com\.br/de-olho-no-zoom/',
        ]

        valid_urls: List[str] = []
        foreign_urls: List[str] = []

        for u in raw_urls:
            if not u or not u.startswith('http'):
                continue

            # Checa se bate com algum padrão de conteúdo genérico/blog
            if any(re.search(pat, u, re.IGNORECASE) for pat in junk_patterns):
                continue

            # Se for amazon internacional (.com, .de) e não amazon.com.br, guarda separado
            if 'amazon.com/' in u or 'amazon.de/' in u or 'amazon.co.uk/' in u:
                foreign_urls.append(u)
            else:
                if u not in valid_urls:
                    valid_urls.append(u)

        # Adiciona domínios internacionais se tivermos poucas URLs brasileiras
        for fu in foreign_urls:
            if len(valid_urls) < 3 and fu not in valid_urls:
                valid_urls.append(fu)

        # Garante links diretos de busca no Mercado Livre e Amazon BR com o termo exato
        encoded_query = urllib.parse.quote_plus(query)
        ml_search_url = f"https://lista.mercadolivre.com.br/{urllib.parse.quote(query.replace(' ', '-'))}"
        amz_search_url = f"https://www.amazon.com.br/s?k={encoded_query}"

        # Se houver menos de 2 páginas diretas de produto, adiciona os links diretos de busca
        if ml_search_url not in valid_urls and len(valid_urls) < 4:
            valid_urls.append(ml_search_url)
        if amz_search_url not in valid_urls and len(valid_urls) < 5:
            valid_urls.append(amz_search_url)

        return valid_urls[:5]

    @classmethod
    def _extract_prices_from_text(cls, text: str) -> Dict[str, Optional[float]]:
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
    def _fallback_market_data(cls, produto_query: str) -> Dict[str, Any]:
        encoded_query = urllib.parse.quote_plus(produto_query)
        ml_query = urllib.parse.quote(produto_query.replace(' ', '-'))
        return {
            "preco_novo_estimado": None,
            "preco_usado_medio": None,
            "urls_referencia": [
                f"https://lista.mercadolivre.com.br/{ml_query}",
                f"https://www.amazon.com.br/s?k={encoded_query}",
                f"https://www.google.com/search?q={encoded_query}+preco+brasil"
            ],
            "snippets_pesquisa": ""
        }


class CopywritingService:
    """
    Serviço de Copywriting Técnico e Honesto (DeepSeek API, Gemini API ou Fallback).
    Gera Título Otimizado, Descrição Estruturada com Ficha Técnica Exata e Sugestão de Preços Justos.
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
            "Você é um redator profissional e especialista técnico em anúncios de desapego e marketplace no Brasil (OLX, Mercado Livre, Facebook).\n"
            "Sua marca registrada é a TRANSPARÊNCIA TOTAL aliada a uma FICHA TÉCNICA PRECISA e COMPLETA.\n"
            "Com base no produto, marca e modelo identificados e nos dados de pesquisa, crie um anúncio de altíssima qualidade técnica.\n\n"
            "ESTRUTURA OBRIGATÓRIA DA DESCRIÇÃO (formate com títulos e tópicos em Markdown):\n"
            "1. 📦 **Visão Geral**: Resumo do produto, marca, modelo e principais destaques e usabilidade.\n"
            "2. 📋 **Ficha Técnica & Especificações Exatas**: Liste as especificações técnicas oficiais e reais do modelo identificado (ex: para áudio/fones: tipo de driver, resposta de frequência, impedância, conector P2/P10/Bluetooth/USB, microfone integrado, isolamento acústico, peso; para instrumentos: madeiras, captação, trastes; para informática/eletrônicos: processador, memória, tela, conexões; para eletros/ferramentas: voltagem, potência em Watts, dimensões, materiais).\n"
            "3. 🔍 **Transparência Total (Estado Real & Detalhes Visíveis)**: Detalhe de forma 100% honesta qualquer marca de uso, arranhão, desgaste ou detalhe apontado pela visão computacional ou pelo vendedor.\n"
            "4. 🎁 **Itens Inclusos**: Liste tudo o que acompanha o produto (cabos, adaptadores, capa, manuais, caixa).\n"
            "5. 🚚 **Condições de Retirada & Envio**: Informações práticas sobre retirada em mãos ou envio seguro.\n\n"
            "Retorne a resposta ESTRITAMENTE em formato JSON com o seguinte schema:\n"
            "{\n"
            '  "titulo": "Título objetivo e atrativo com marca, modelo e atributo principal (max 70 chars)",\n'
            '  "slug": "Slug amigável, simples, curto e limpo em minúsculas com hífens baseado no produto, marca e modelo (ex: \'fone-sennheiser-hd-400s\', \'camera-sony-a6400\', \'violao-yamaha-c40\')",\n'
            '  "descricao": "Texto completo da descrição seguindo a estrutura de tópicos acima",\n'
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
            "Você é um redator profissional e especialista técnico em anúncios de desapego e marketplace no Brasil.\n"
            "Crie um anúncio de altíssima qualidade com TRANSPARÊNCIA TOTAL e FICHA TÉCNICA PRECISA do modelo identificado.\n\n"
            f"Dados Visuais: {json.dumps(vision_data, ensure_ascii=False)}\n"
            f"Pesquisa de Mercado: {json.dumps(market_data, ensure_ascii=False)}\n"
            f"Observações do Vendedor: {observacoes}\n\n"
            "A descrição DEVE conter:\n"
            "- 📦 Visão Geral\n"
            "- 📋 Ficha Técnica & Especificações Exatas (com dados reais e detalhados do modelo identificado)\n"
            "- 🔍 Transparência Total (Estado Real & Detalhes Visíveis)\n"
            "- 🎁 Itens Inclusos\n"
            "- 🚚 Condições de Retirada & Envio\n\n"
            "Retorne ESTRITAMENTE em formato JSON com as chaves:\n"
            "titulo (string até 70 chars), slug (slug amigável curto em minúsculas com hífens como 'fone-sennheiser-hd-400s'), descricao (string completa), preco_usado (float), preco_novo (float), preco_aluguel (float)."
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
        modelo = vision_data.get('modelo', '')
        defeitos = vision_data.get('defeitos_visiveis', 'Em bom estado geral com marcas leves de uso.')
        acessorios = vision_data.get('acessorios_visiveis', 'Itens exibidos nas fotos.')
        specs = vision_data.get('especificacoes_visiveis', 'Conforme exibido nas imagens.')

        preco_novo = market_data.get('preco_novo_estimado') or 250.00
        preco_usado = market_data.get('preco_usado_medio') or round(preco_novo * 0.6, 2)
        preco_aluguel = round(preco_usado * 0.15, 2)

        descricao = (
            f"📦 **Visão Geral:**\n"
            f"{prod} ({marca} {modelo}). Excelente oportunidade para aquisição com ótimo custo-benefício.\n\n"
            f"📋 **Ficha Técnica & Especificações:**\n"
            f"• Marca: {marca}\n"
            f"• Modelo: {modelo}\n"
            f"• Estado: {vision_data.get('estado_conservacao', 'Bom estado').capitalize()}\n"
            f"• Especificações: {specs}\n\n"
            f"🔍 **Transparência Total (Estado Real & Detalhes Visíveis):**\n"
            f"{defeitos}\n\n"
            f"🎁 **Itens Inclusos:**\n"
            f"{acessorios}\n\n"
            f"{'📝 Observação do Vendedor: ' + observacoes if observacoes else ''}\n\n"
            f"🚚 **Condições de Retirada & Envio:**\n"
            f"Retirada em mãos a combinar ou envio seguro para todo o Brasil. Pagamento via PIX.\n\n"
            f"💬 *Fique à vontade para tirar dúvidas e negociar através dos nossos canais de contato!*"
        )

        # Monta título limpo sem redundâncias
        titulo_parts = []
        if prod and prod.lower() not in ['genérica / não identificada', 'padrão', 'item avaliado', 'item em análise', 'produto em desapego']:
            titulo_parts.append(prod)
        if marca and marca.lower() not in ['genérica / não identificada', 'padrão', 'outros', 'desconhecido', 'desconhecida'] and marca.lower() not in prod.lower():
            titulo_parts.append(marca)
        if modelo and modelo.lower() not in ['genérica / não identificada', 'padrão', 'outros', 'desconhecido', 'desconhecida'] and modelo.lower() not in prod.lower():
            titulo_parts.append(modelo)

        titulo = " ".join(titulo_parts)[:70].strip() if titulo_parts else (prod or "Item em Desapego")

        # Gera sugestão de slug limpo e conciso
        slug_sugerido = slugify(titulo)[:60].strip('-') or "item"

        return {
            "titulo": titulo,
            "slug": slug_sugerido,
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
    1. Visão Computacional -> 2. Pesquisa de Mercado & Ficha Técnica -> 3. Copywriting Técnico -> 4. Notificação
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

        # Passo 2: Construção da Query Otimizada e Pesquisa de Mercado
        search_query = MarketSearchService.build_search_query(vision_result, item.titulo)
        logger.info(f"Query otimizada construída para busca de mercado: '{search_query}'")
        market_result = MarketSearchService.search_market_prices(search_query)

        # Passo 3: Copywriting com Ficha Técnica Exata e Transparência Total
        copy_result = CopywritingService.generate_listing_copy(
            vision_data=vision_result,
            market_data=market_result,
            observacoes_vendedor=item.defeitos_visiveis or ""
        )

        # Atualização do Modelo Item
        if copy_result.get('titulo'):
            item.titulo = copy_result['titulo']

        # Atualização inteligente do slug (URL amigável)
        suggested_slug = copy_result.get('slug')
        if suggested_slug:
            item.slug = item.generate_unique_slug(suggested_slug)
        elif copy_result.get('titulo') and (not item.slug or item.slug.startswith('item-em-analise')):
            item.slug = item.generate_unique_slug(copy_result['titulo'])

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

        def format_currency(val):
            if val is not None:
                return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return "-"

        return {
            "success": True,
            "item_id": item.id,
            "titulo": item.titulo,
            "slug": item.slug,
            "preco_usado": str(item.preco_usado) if item.preco_usado is not None else None,
            "preco_usado_formatado": format_currency(item.preco_usado),
            "preco_novo_referencia": str(item.preco_novo_referencia) if item.preco_novo_referencia is not None else None,
            "preco_novo_formatado": format_currency(item.preco_novo_referencia),
            "preco_aluguel": str(item.preco_aluguel) if item.preco_aluguel is not None else None,
            "categoria": item.categoria,
            "categoria_display": item.get_categoria_display(),
            "estado_conservacao": item.estado_conservacao,
            "estado_conservacao_display": item.get_estado_conservacao_display(),
            "defeitos_visiveis": item.defeitos_visiveis,
            "descricao_ia": item.descricao_ia,
            "urls_referencia": item.urls_referencia or [],
            "num_urls": len(item.urls_referencia) if item.urls_referencia else 0,
            "vision_data": vision_result,
            "market_data": {
                "preco_novo_estimado": market_result.get("preco_novo_estimado"),
                "preco_usado_medio": market_result.get("preco_usado_medio"),
                "urls_count": len(market_result.get("urls_referencia", []))
            }
        }
