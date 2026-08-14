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


class SerpApiService:
    """
    Serviço de consulta de cota e status da conta SerpApi (Google Lens).
    """
    _cached_quota: Optional[Dict[str, Any]] = None
    _cached_time: float = 0.0

    @classmethod
    def get_account_quota(cls) -> Dict[str, Any]:
        import time
        now = time.time()
        # Cache por 60 segundos para evitar chamadas redundantes
        if cls._cached_quota and (now - cls._cached_time < 60):
            return cls._cached_quota

        api_config = getattr(settings, 'AI_CONFIG', {})
        serpapi_key = api_config.get('SERPAPI_API_KEY')
        if not serpapi_key:
            return {"available": False, "searches_left": 0, "searches_total": 0, "formatted": ""}

        try:
            r = requests.get('https://serpapi.com/account', params={'api_key': serpapi_key}, timeout=5)
            if r.status_code == 200:
                d = r.json()
                left = d.get('total_searches_left', d.get('plan_searches_left', 0))
                total = d.get('searches_per_month', 250)
                used = d.get('this_month_usage', 0)
                quota_data = {
                    "available": True,
                    "searches_left": left,
                    "searches_total": total,
                    "this_month_usage": used,
                    "formatted": f"{left}/{total} rest."
                }
                cls._cached_quota = quota_data
                cls._cached_time = now
                return quota_data
        except Exception as e:
            logger.warning(f"Erro ao consultar cota SerpApi: {e}")

        return {"available": False, "searches_left": 0, "searches_total": 0, "formatted": ""}


class VisualSearchService:
    """
    Serviço de Busca Visual Reversa (Estilo Google Lens / Google Cloud Vision / SerpApi).
    Analisa fotos reais para encontrar correspondências visuais exatas no catálogo da web,
    identificando códigos de modelo específicos (ex: 'Tomate MTG-164'), marcas reais e links diretos.
    """
    @classmethod
    def search_by_image(cls, item: Item, use_serpapi: bool = False) -> Dict[str, Any]:
        api_config = getattr(settings, 'AI_CONFIG', {})
        google_vision_key = api_config.get('GOOGLE_VISION_API_KEY')
        gemini_key = api_config.get('GEMINI_API_KEY')
        serpapi_key = api_config.get('SERPAPI_API_KEY')

        # Coleta imagens locais válidas do item
        imagens = [img for img in item.imagens.all() if hasattr(img, 'imagem') and img.imagem and os.path.exists(img.imagem.path)]
        if not imagens:
            return {
                "success": False,
                "provider": "none",
                "produto_identificado": "",
                "marca": "",
                "modelo": "",
                "ocr_text": "",
                "entidades": [],
                "labels": [],
                "urls_diretas": []
            }

        # 1. Modo On-Demand Premium: SerpApi Google Lens (se acionado explicitamente pelo botão)
        if use_serpapi and serpapi_key:
            try:
                res = cls._call_serpapi_google_lens(imagens[0].imagem.path, serpapi_key)
                if res.get('success'):
                    logger.info(f"SerpApi Google Lens (On-Demand) identificou: '{res.get('produto_identificado')}' ({len(res.get('urls_diretas', []))} URLs)")
                    return res
            except Exception as e:
                logger.error(f"Erro no SerpApi Google Lens: {e}")

        # 2. Modo Padrão Gratuito: Google Lens Nativo (chrome-lens-py / Chromium Protobuf Engine - 100% grátis)
        lens_native_res = cls._call_chrome_lens_native(imagens[0].imagem.path)
        if lens_native_res.get('success') and lens_native_res.get('ocr_text'):
            logger.info(f"Google Lens Nativo detectou OCR: '{lens_native_res.get('ocr_text')}'")
            return lens_native_res

        # 3. Modo Padrão Gratuito: Google Cloud Vision WEB_DETECTION + OCR + Labels (1.000 requisições grátis/mês)
        if google_vision_key:
            try:
                res = cls._call_google_vision_web_detection(imagens[0].imagem.path, google_vision_key)
                if res.get('success'):
                    return res
            except Exception as e:
                logger.error(f"Erro no Google Cloud Vision Web Detection: {e}")

        # 4. Modo Padrão Gratuito: Gemini 3.7 Flash com Grounding Multimodal
        if gemini_key:
            try:
                res = cls._call_gemini_grounded_vision(imagens, gemini_key, item)
                if res.get('success'):
                    return res
            except Exception as e:
                logger.error(f"Erro no Gemini Grounded Vision: {e}")

        return lens_native_res if lens_native_res.get('success') else {
            "success": False,
            "provider": "none",
            "produto_identificado": "",
            "marca": "",
            "modelo": "",
            "ocr_text": "",
            "entidades": [],
            "labels": [],
            "urls_diretas": []
        }

    @classmethod
    def _call_chrome_lens_native(cls, image_path: str) -> Dict[str, Any]:
        """
        Executa a leitura direta do Google Lens usando o motor de Protobuf do Chromium (chrome-lens-py).
        Zero chaves de API necessárias, zero custo, direto no Python.
        """
        try:
            from chrome_lens_py import LensAPI
            import asyncio
            
            async def _run():
                lens = LensAPI()
                return await lens.process_image(image_path)
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        res = pool.submit(asyncio.run, _run()).result()
                else:
                    res = loop.run_until_complete(_run())
            except Exception:
                res = asyncio.run(_run())

            ocr_text = ""
            if isinstance(res, dict):
                ocr_text = res.get('ocr_text', '').strip()
            
            marca = ""
            modelo = ""
            if ocr_text:
                words = ocr_text.split()
                if len(words) == 1:
                    marca = words[0].capitalize()
                elif len(words) >= 2:
                    marca = words[0].capitalize()
                    modelo = " ".join(words[1:])
            
            return {
                "success": bool(ocr_text),
                "provider": "google_lens_native",
                "ocr_text": ocr_text,
                "produto_identificado": ocr_text,
                "marca": marca,
                "modelo": modelo,
                "entidades": [ocr_text] if ocr_text else [],
                "labels": [],
                "urls_diretas": []
            }
        except Exception as e:
            logger.warning(f"Google Lens nativo: {e}")
            return {"success": False, "provider": "google_lens_native"}

    @classmethod
    def _call_google_vision_web_detection(cls, image_path: str, api_key: str) -> Dict[str, Any]:
        """
        Envia a imagem em Base64 para a Google Cloud Vision API com WEB_DETECTION, TEXT_DETECTION e LABEL_DETECTION.
        Retorna rótulos de melhor estimativa (bestGuessLabels), textos lidos por OCR, entidades e páginas com imagens correspondentes.
        """
        with open(image_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")

        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
        payload = {
            "requests": [
                {
                    "image": {"content": b64_img},
                    "features": [
                        {"type": "WEB_DETECTION", "maxResults": 10},
                        {"type": "TEXT_DETECTION", "maxResults": 10},
                        {"type": "LABEL_DETECTION", "maxResults": 10}
                    ]
                }
            ]
        }
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        responses = data.get("responses", [])
        if not responses:
            return {"success": False, "provider": "google_vision"}

        first_resp = responses[0]
        web_detection = first_resp.get("webDetection", {})
        text_annotations = first_resp.get("textAnnotations", [])
        label_annotations = first_resp.get("labelAnnotations", [])

        # OCR: texto completo lido na imagem
        ocr_text = text_annotations[0].get("description", "").strip() if text_annotations else ""

        # Labels visuais
        labels = [l.get("description", "").strip() for l in label_annotations if l.get("description")]

        # Rótulo de melhor estimativa do Google
        best_guess = ""
        best_guess_labels = web_detection.get("bestGuessLabels", [])
        if best_guess_labels:
            best_guess = best_guess_labels[0].get("label", "").strip()

        # Entidades da web identificadas
        entities = [
            e.get("description", "").strip()
            for e in web_detection.get("webEntities", [])
            if e.get("description")
        ]

        # URLs diretas de páginas que contêm a foto ou imagem idêntica
        matching_pages = web_detection.get("pagesWithMatchingImages", [])
        direct_urls = []
        for p in matching_pages:
            u = p.get("url")
            if u and u.startswith("http") and u not in direct_urls:
                direct_urls.append(u)

        # Categorias genéricas em inglês que não devem ser tratadas como marca/modelo
        generic_categories = {
            'electronics', 'electronic device', 'hardware', 'gadget', 'technology',
            'shoe', 'plastic bottle', 'bottle', 'water', 'furniture', 'appliance',
            'audio equipment', 'headphones', 'table', 'desk', 'product'
        }

        # Extração de marca e modelo prováveis a partir do best_guess e entidades
        marca = ""
        modelo = ""
        produto_identificado = ""

        if best_guess and best_guess.lower() not in generic_categories:
            produto_identificado = best_guess
            words = best_guess.split()
            if len(words) > 1:
                marca = words[0].capitalize()
                modelo = " ".join(words[1:])
            else:
                modelo = best_guess
        elif entities:
            # Pega a primeira entidade que não seja categoria genérica
            specific_entities = [e for e in entities if e.lower() not in generic_categories]
            if specific_entities:
                produto_identificado = specific_entities[0]
                if len(specific_entities) > 1:
                    marca = specific_entities[1]

        return {
            "success": bool(produto_identificado or direct_urls or ocr_text or entities),
            "provider": "google_vision_web_detection",
            "produto_identificado": produto_identificado,
            "marca": marca,
            "modelo": modelo,
            "ocr_text": ocr_text,
            "entidades": entities[:8],
            "labels": labels[:8],
            "urls_diretas": direct_urls[:6]
        }

    @classmethod
    def _call_gemini_grounded_vision(cls, imagens, api_key: str, item: Item) -> Dict[str, Any]:
        """
        Usa o Gemini 3.7 Flash com Grounding do Google Search para cruzar imagens com a web.
        """
        candidate_models = ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-flash-latest"]
        parts = []
        prompt = (
            "Você é um especialista em busca reversa visual (estilo Google Lens).\n"
            "Analise estas fotos e use a ferramenta de busca do Google para encontrar o produto e modelo comercial EXATO no mercado brasileiro.\n"
            "Identifique:\n"
            "1. Nome completo e comercial do produto\n"
            "2. Marca real do fabricante\n"
            "3. Modelo exato (incluindo códigos como MTG-164, HD 400S, C40, etc.)\n"
            "4. Categoria mais adequada\n"
            "5. Links de referência de lojas ou marketplaces brasileiros onde este produto é vendido.\n\n"
            "Responda estritamente em formato JSON com as chaves:\n"
            "{\n"
            '  "produto_identificado": "string",\n'
            '  "marca": "string",\n'
            '  "modelo": "string",\n'
            '  "categoria_sugerida": "string",\n'
            '  "urls_referencia": ["url1", "url2"]\n'
            "}"
        )
        parts.append({"text": prompt})

        for img_obj in imagens[:3]:
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
            "tools": [{"google_search": {}}],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        last_error = None
        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                resp = requests.post(url, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                candidate = data.get('candidates', [{}])[0]
                text = candidate.get('content', {}).get('parts', [{}])[0].get('text', '{}')
                parsed = json.loads(text)

                grounding_metadata = candidate.get('groundingMetadata', {})
                grounding_chunks = grounding_metadata.get('groundingChunks', [])
                grounding_urls = [
                    ch.get('web', {}).get('uri')
                    for ch in grounding_chunks
                    if ch.get('web', {}).get('uri')
                ]

                urls = parsed.get('urls_referencia', [])
                for gu in grounding_urls:
                    if gu not in urls:
                        urls.append(gu)

                return {
                    "success": True,
                    "provider": "gemini_grounded_vision",
                    "produto_identificado": parsed.get('produto_identificado', ''),
                    "marca": parsed.get('marca', ''),
                    "modelo": parsed.get('modelo', ''),
                    "entidades": [parsed.get('marca', ''), parsed.get('modelo', '')],
                    "labels": [],
                    "ocr_text": "",
                    "urls_diretas": urls[:6],
                    "categoria_sugerida": parsed.get('categoria_sugerida', '')
                }
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        return {"success": False, "provider": "gemini_grounded_vision"}

    @classmethod
    def _call_serpapi_google_lens(cls, image_path: str, api_key: str) -> Dict[str, Any]:
        """
        Executa a pesquisa visual na SerpApi usando a engine oficial 'google_lens'.
        Redimensiona automaticamente com Pillow para garantir tamanho < 500KB.
        """
        import io
        from PIL import Image

        # Redimensiona para max 800x800 e comprime em JPEG (< 500KB)
        im = Image.open(image_path)
        im.thumbnail((800, 800))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=85)
        buf.seek(0)

        upload_url = "https://serpapi.com/image"
        upload_resp = requests.post(
            upload_url,
            files={"image": ("image.jpg", buf, "image/jpeg")},
            data={"api_key": api_key},
            timeout=25
        )
        upload_resp.raise_for_status()
        upload_data = upload_resp.json()
        image_id = upload_data.get("image_id")

        if not image_id:
            return {"success": False, "provider": "serpapi_lens"}

        search_url = "https://serpapi.com/search.json"
        params = {
            "api_key": api_key,
            "engine": "google_lens",
            "image_id": image_id
        }
        resp = requests.get(search_url, params=params, timeout=30)
        resp.raise_for_status()
        res_data = resp.json()

        visual_matches = res_data.get("visual_matches", [])
        related_content = res_data.get("related_content", [])
        organic_results = res_data.get("organic_results", [])

        urls = []
        titles = []
        for vm in visual_matches:
            if vm.get("link") and vm.get("link").startswith("http") and vm.get("link") not in urls:
                urls.append(vm.get("link"))
            if vm.get("title") and vm.get("title") not in titles:
                titles.append(vm.get("title"))

        for org in organic_results:
            if org.get("link") and org.get("link").startswith("http") and org.get("link") not in urls:
                urls.append(org.get("link"))
            if org.get("title") and org.get("title") not in titles:
                titles.append(org.get("title"))

        for rc in related_content:
            if rc.get("query") and rc.get("query") not in titles:
                titles.append(rc.get("query"))

        best_title = titles[0] if titles else ""
        marca = ""
        modelo = ""
        if titles:
            # Extrai primeira marca/modelo provável
            words = titles[0].split()
            if len(words) > 1:
                marca = words[0].capitalize()
                modelo = " ".join(words[1:4])

        return {
            "success": bool(urls or titles),
            "provider": "serpapi_google_lens",
            "produto_identificado": best_title,
            "marca": marca,
            "modelo": modelo,
            "entidades": titles[:8],
            "labels": [],
            "ocr_text": "",
            "urls_diretas": urls[:6]
        }


class VisionService:
    """
    Serviço de Visão Computacional (Gemini Flash ou Google Cloud Vision + DeepSeek Reasoner).
    Analisa fotos para identificar produto, marca, modelo exato, defeitos visíveis e acessórios.
    """
    @classmethod
    def analyze_item_images(cls, item: Item, visual_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        api_config = getattr(settings, 'AI_CONFIG', {})
        gemini_key = api_config.get('GEMINI_API_KEY')
        deepseek_key = api_config.get('DEEPSEEK_API_KEY')

        # Coleta imagens
        imagens = item.imagens.all()
        if not imagens.exists():
            return cls._fallback_vision_data(item, "Nenhuma foto fornecida.", visual_hint=visual_hint)

        # 1. Tenta Gemini Vision se configurado
        if gemini_key:
            try:
                return cls._call_gemini_vision(imagens, gemini_key, item, visual_hint=visual_hint)
            except Exception as e:
                logger.warning(f"Gemini Vision indisponível ou quota esgotada: {e}")

        # 2. Tenta DeepSeek Reasoner alimentado por Google Vision (OCR + Labels + Entidades)
        if deepseek_key and visual_hint and visual_hint.get("success"):
            try:
                return cls._call_deepseek_vision_reasoning(deepseek_key, item, visual_hint)
            except Exception as e:
                logger.error(f"Erro no DeepSeek Vision Reasoning: {e}")

        # Fallback inteligente
        return cls._fallback_vision_data(item, visual_hint=visual_hint)

    @classmethod
    def _call_gemini_vision(cls, imagens, api_key: str, item: Item, visual_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        candidate_models = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
        parts = []

        hint_text = ""
        if visual_hint and visual_hint.get("produto_identificado"):
            hint_text = (
                f"\n[DICA DE CORRESPONDÊNCIA VISUAL - GOOGLE LENS / WEB DETECTION]:\n"
                f"Possível produto identificado: '{visual_hint.get('produto_identificado')}'. "
                f"Marca sugerida: '{visual_hint.get('marca')}', Modelo sugerido: '{visual_hint.get('modelo')}'. "
                f"OCR detectado: '{visual_hint.get('ocr_text', '')}'.\n"
            )

        system_instruction = (
            "Você é um perito em avaliação visual e técnica de itens usados para venda e desapego no Brasil. "
            "Analise as fotos com extrema atenção aos detalhes visuais, inscrições de texto, logotipos, modelo e serigrafias no produto.\n"
            f"{hint_text}"
            "Identifique com precisão:\n"
            "1. Produto identificado completo com tipo e função principal\n"
            "2. Marca exata do fabricante\n"
            "3. Modelo exato (ex: HD 400S, C40, MTG-164, WH-1000XM4, iPhone 13 128GB, etc.)\n"
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
    def _call_deepseek_vision_reasoning(cls, api_key: str, item: Item, visual_hint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpreta dados estruturados de visão computacional (OCR, entidades, rótulos) usando o DeepSeek LLM.
        """
        url = "https://api.deepseek.com/chat/completions"
        system_prompt = (
            "Você é um perito em identificação de produtos para venda e desapego no Brasil.\n"
            "Analise os dados visuais extraídos por visão computacional (OCR, detecção de texto na foto, rótulos e entidades web) "
            "e identifique com precisão o produto, marca, modelo real e categoria.\n\n"
            "Responda estritamente em formato JSON com as chaves:\n"
            "{\n"
            '  "produto_identificado": "Nome claro do produto",\n'
            '  "marca": "Marca identificada ou Genérica",\n'
            '  "modelo": "Modelo ou código específico",\n'
            '  "categoria_sugerida": "uma entre: eletronicos, moveis, eletrodomesticos, ferramentas, instrumentos, vestuario, esportes, livros, outros",\n'
            '  "estado_conservacao": "um entre: novo, excelente, bom, marcas_uso, defeito_reparo",\n'
            '  "defeitos_visiveis": "descrição honesta de marcas de uso",\n'
            '  "acessorios_visiveis": "acessórios identificados",\n'
            '  "especificacoes_visiveis": "especificações perceptíveis"\n'
            "}"
        )

        user_content = json.dumps({
            "titulo_informado": item.titulo,
            "observacoes_vendedor": item.defeitos_visiveis or "",
            "texto_lido_ocr": visual_hint.get("ocr_text", ""),
            "rotulos_visuais": visual_hint.get("labels", []),
            "entidades_web": visual_hint.get("entidades", []),
            "produto_identificado_lens": visual_hint.get("produto_identificado", "")
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
        resp = requests.post(url, json=payload, headers=headers, timeout=25)
        resp.raise_for_status()
        return json.loads(resp.json()['choices'][0]['message']['content'])

    @classmethod
    def _fallback_vision_data(cls, item: Item, motivo: str = "", visual_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        nome = item.titulo if not item.titulo.startswith("Item em análise") else "Item Avaliado"
        marca = "Genérica / Não identificada"
        modelo = "Padrão"

        if visual_hint and visual_hint.get("produto_identificado"):
            nome = visual_hint.get("produto_identificado")
            if visual_hint.get("marca"):
                marca = visual_hint.get("marca")
            if visual_hint.get("modelo"):
                modelo = visual_hint.get("modelo")

        return {
            "produto_identificado": nome,
            "marca": marca,
            "modelo": modelo,
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
    def build_search_query(cls, vision_data: Dict[str, Any], fallback_title: str = "", visual_hint: Optional[Dict[str, Any]] = None) -> str:
        """
        Gera uma query precisa e otimizada unindo Marca, Modelo e Tipo de Produto,
        evitando termos genéricos ou redundâncias.
        """
        marca = (vision_data.get('marca') or '').strip()
        modelo = (vision_data.get('modelo') or '').strip()
        produto = (vision_data.get('produto_identificado') or '').strip()

        generic_placeholders = {
            'generica', 'genérica', 'generica / nao identificada', 'genérica / não identificada',
            'padrao', 'padrão', 'item avaliado', 'item em análise', 'outros', 'desconhecido', 'desconhecida',
            'electronics', 'electronic device', 'hardware', 'gadget', 'technology',
            'shoe', 'plastic bottle', 'bottle', 'water', 'furniture', 'appliance',
            'audio equipment', 'table', 'desk', 'product'
        }

        # Se tiver dica visual de modelo exato (ex: Tomate MTG-164), usa para enriquecer
        if visual_hint and visual_hint.get("produto_identificado"):
            vh_prod = visual_hint.get("produto_identificado")
            if vh_prod.lower() not in generic_placeholders and len(vh_prod) > len(produto):
                produto = vh_prod
            if visual_hint.get("marca") and visual_hint.get("marca").lower() not in generic_placeholders:
                marca = visual_hint.get("marca")
            if visual_hint.get("modelo") and visual_hint.get("modelo").lower() not in generic_placeholders:
                modelo = visual_hint.get("modelo")

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
    def search_market_prices(cls, produto_query: str, visual_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        api_config = getattr(settings, 'AI_CONFIG', {})
        tavily_key = api_config.get('TAVILY_API_KEY')
        serper_key = api_config.get('SERPER_API_KEY')

        if tavily_key:
            try:
                return cls._call_tavily(produto_query, tavily_key, visual_urls=visual_urls)
            except Exception as e:
                logger.error(f"Erro na API Tavily: {e}")

        if serper_key:
            try:
                return cls._call_serper(produto_query, serper_key, visual_urls=visual_urls)
            except Exception as e:
                logger.error(f"Erro na API Serper: {e}")

        # Fallback de busca de mercado
        return cls._fallback_market_data(produto_query, visual_urls=visual_urls)

    @classmethod
    def _call_tavily(cls, query: str, api_key: str, visual_urls: Optional[List[str]] = None) -> Dict[str, Any]:
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
        filtered_urls = cls._filter_and_rank_urls(raw_urls, query, visual_urls=visual_urls)

        return {
            "preco_novo_estimado": precos.get('preco_novo'),
            "preco_usado_medio": precos.get('preco_usado'),
            "urls_referencia": filtered_urls,
            "snippets_pesquisa": all_snippets[:2000]
        }

    @classmethod
    def _call_serper(cls, query: str, api_key: str, visual_urls: Optional[List[str]] = None) -> Dict[str, Any]:
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
        filtered_urls = cls._filter_and_rank_urls(raw_urls, query, visual_urls=visual_urls)

        return {
            "preco_novo_estimado": precos.get('preco_novo'),
            "preco_usado_medio": precos.get('preco_usado'),
            "urls_referencia": filtered_urls,
            "snippets_pesquisa": all_snippets[:2000]
        }

    @classmethod
    def _filter_and_rank_urls(cls, raw_urls: List[str], query: str, visual_urls: Optional[List[str]] = None) -> List[str]:
        """
        Filtra URLs genéricas, de blog, listas de mais vendidos e nós vazios.
        Prioriza páginas diretas de produto obtidas por Busca Visual Reversa (Google Lens / Vision).
        Evita links de busca genéricos (/s?k=...) quando houver links de produtos reais catalogados.
        """
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

        # 1. Prioridade Máxima: URLs diretas vindas da Busca Visual Reversa
        if visual_urls:
            for vu in visual_urls:
                if not vu or not vu.startswith('http'):
                    continue
                if any(re.search(pat, vu, re.IGNORECASE) for pat in junk_patterns):
                    continue
                if vu not in valid_urls:
                    valid_urls.append(vu)

        # 2. URLs orgânicas da busca de mercado
        for u in raw_urls:
            if not u or not u.startswith('http'):
                continue
            if any(re.search(pat, u, re.IGNORECASE) for pat in junk_patterns):
                continue
            if 'amazon.com/' in u or 'amazon.de/' in u or 'amazon.co.uk/' in u:
                foreign_urls.append(u)
            else:
                if u not in valid_urls:
                    valid_urls.append(u)

        # Adiciona domínios internacionais se tivermos poucas URLs brasileiras
        for fu in foreign_urls:
            if len(valid_urls) < 3 and fu not in valid_urls:
                valid_urls.append(fu)

        # 3. Só adiciona links diretos de busca no ML/Amazon se tivermos MENOS de 2 páginas de produto
        if len(valid_urls) < 2 and query:
            encoded_query = urllib.parse.quote_plus(query)
            ml_search_url = f"https://lista.mercadolivre.com.br/{urllib.parse.quote(query.replace(' ', '-'))}"
            amz_search_url = f"https://www.amazon.com.br/s?k={encoded_query}"
            if ml_search_url not in valid_urls:
                valid_urls.append(ml_search_url)
            if amz_search_url not in valid_urls:
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
    def infer_category(cls, text: str) -> str:
        """
        Deduz automaticamente a categoria mais apropriada do modelo Item.Categoria
        a partir do nome do produto, modelo ou descrição pesquisada.
        """
        if not text:
            return Item.Categoria.OUTROS

        t = text.lower()

        # Instrumentos Musicais
        if any(w in t for w in [
            'violao', 'violão', 'guitarra', 'baixo', 'contrabaixo', 'teclado', 'piano', 'ukulele',
            'bateria', 'prato', 'afinador', 'pedal', 'pedaleira', 'encordoamento', 'saxofone',
            'flauta', 'microfone', 'shure', 'sennheiser', 'amplificador', 'cabo p10', 'cavaquinho',
            'sanfona', 'acordeon', 'tarraxa', 'pedalboard', 'gaita', 'trompete', 'clarinete', 'yamaha c40', 'yamaha'
        ]):
            return Item.Categoria.INSTRUMENTOS

        # Eletrônicos & Informática
        if any(w in t for w in [
            'fone', 'headphone', 'headset', 'celular', 'smartphone', 'iphone', 'galaxy', 'xiaomi',
            'motorola', 'notebook', 'laptop', 'computador', 'pc gamer', 'tablet', 'ipad', 'monitor',
            'mouse', 'teclado mecanico', 'teclado sem fio', 'smartwatch', 'apple watch', 'carregador',
            'cabo usb', 'hd externo', 'ssd', 'placa de video', 'rtx', 'gtx', 'geforce', 'processador',
            'ryzen', 'intel core', 'roteador', 'roteador wi-fi', 'tv ', 'smart tv', 'camera', 'câmera',
            'drone', 'gopro', 'kindle', 'alexa', 'echo dot', 'soundbar', 'jbl', 'airpods'
        ]):
            return Item.Categoria.ELETRONICOS

        # Ferramentas e Casa
        if any(w in t for w in [
            'furadeira', 'parafusadeira', 'serra', 'martelete', 'lixadeira', 'trena', 'alicate',
            'chave de fenda', 'chave philips', 'esmerilhadeira', 'multimetro', 'multímetro',
            'ferro de solda', 'makita', 'bosch', 'dewalt', 'black+decker', 'black decker', 'dremel',
            'compressor', 'nivel a laser', 'nível a laser', 'bancada', 'morsa', 'soprador termico'
        ]):
            return Item.Categoria.FERRAMENTAS

        # Eletrodomésticos
        if any(w in t for w in [
            'cafeteira', 'air fryer', 'fritadeira', 'liquidificador', 'batedeira', 'microondas',
            'micro-ondas', 'forno', 'aspirador', 'ventilador', 'ferro de passar', 'geladeira',
            'refrigerador', 'fogao', 'fogão', 'cooktop', 'purificador', 'sanduicheira', 'mixer',
            'torradeira', 'lavadora', 'lava e seca', 'adega', 'climatizador', 'ar-condicionado'
        ]):
            return Item.Categoria.ELETRODOMESTICOS

        # Móveis e Decoração
        if any(w in t for w in [
            'cadeira', 'cadeira gamer', 'cadeira de escritorio', 'mesa', 'escrivaninha', 'sofa', 'sofá',
            'estante', 'rack', 'poltrona', 'armario', 'armário', 'comoda', 'cômoda', 'cama', 'colchao',
            'colchão', 'criado mudo', 'mesa de cabeceira', 'prateleira', 'suporte articulado', 'lustre', 'luminaria'
        ]):
            return Item.Categoria.MOVEIS

        # Roupas e Acessórios
        if any(w in t for w in [
            'tenis', 'tênis', 'sapato', 'bota', 'sandalia', 'sandália', 'chinelo', 'camiseta',
            'camisa', 'jaqueta', 'casaco', 'moletom', 'calca', 'calça', 'bermuda', 'shorts',
            'vestido', 'saia', 'bolsa', 'mochila', 'mala', 'relogio', 'relógio', 'oculos', 'óculos',
            'bone', 'boné', 'cinto', 'carteira'
        ]):
            return Item.Categoria.VESTUARIO

        # Esportes e Lazer
        if any(w in t for w in [
            'bicicleta', 'bike', 'esteira', 'halteres', 'halter', 'anilha', 'barra fixa', 'bola',
            'raquete', 'patins', 'skate', 'longboard', 'prancha', 'surf', 'barraca', 'camping',
            'saco de dormir', 'suplemento', 'whey', 'creatina', 'kimono', 'capacete bike'
        ]):
            return Item.Categoria.ESPORTES

        # Livros e Colecionáveis
        if any(w in t for w in [
            'livro', 'box', 'quadrinhos', 'manga', 'mangá', 'gibi', 'revista', 'enciclopedia',
            'hq', 'card game', 'board game', 'action figure', 'colecionavel', 'colecionável',
            'harry potter', 'tolkien', 'senhor dos aneis', 'star wars', 'capa dura', 'literatura'
        ]):
            return Item.Categoria.LIVROS

        return Item.Categoria.OUTROS

    @classmethod
    def search_internet_products(cls, query: str) -> Dict[str, Any]:
        """
        Pesquisa ao vivo na internet produtos correspondentes ao termo digitado no título.
        Retorna lista de anúncios e produtos do catálogo nacional com preços em R$, imagens, links e sugestões.
        """
        query_clean = (query or '').strip()
        if len(query_clean) < 2:
            return {
                "success": False,
                "query": query_clean,
                "total": 0,
                "items": [],
                "suggestion": {}
            }

        api_config = getattr(settings, 'AI_CONFIG', {})
        serper_key = api_config.get('SERPER_API_KEY')
        tavily_key = api_config.get('TAVILY_API_KEY')

        items: List[Dict[str, Any]] = []
        found_prices_new: List[float] = []
        found_prices_used: List[float] = []
        reference_urls: List[str] = []
        all_snippets: List[str] = []

        def clean_price_val(raw_price: Any) -> Optional[float]:
            if raw_price is None:
                return None
            if isinstance(raw_price, (int, float)):
                return float(raw_price)
            if isinstance(raw_price, str):
                m = re.search(r'R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)', raw_price)
                if m:
                    try:
                        return float(m.group(1).replace('.', '').replace(',', '.'))
                    except ValueError:
                        pass
                m2 = re.search(r'(\d+[\.,]\d{2})', raw_price)
                if m2:
                    try:
                        return float(m2.group(1).replace(',', '.'))
                    except ValueError:
                        pass
            return None

        def format_currency_brl(val: Optional[float]) -> str:
            if val is not None and val > 0:
                return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return ""

        # 1. Google Shopping via Serper (Catálogo de Preços e Produtos no Brasil)
        if serper_key:
            try:
                shop_resp = requests.post(
                    "https://google.serper.dev/shopping",
                    json={"q": query_clean, "gl": "br", "hl": "pt-br", "num": 8},
                    headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                    timeout=8
                )
                if shop_resp.status_code == 200:
                    shop_data = shop_resp.json()
                    for s in shop_data.get('shopping', []):
                        title = s.get('title', '').strip()
                        price_num = clean_price_val(s.get('price'))
                        source = s.get('source', '').strip() or 'Google Shopping'
                        link = s.get('link', '')
                        img_url = s.get('imageUrl', '')

                        if not title:
                            continue

                        if price_num and price_num > 5:
                            if 'usado' in title.lower() or 'usado' in source.lower() or 'olx' in source.lower():
                                found_prices_used.append(price_num)
                            else:
                                found_prices_new.append(price_num)

                        if link and link.startswith('http') and link not in reference_urls:
                            reference_urls.append(link)

                        items.append({
                            "title": title,
                            "price": price_num,
                            "price_formatted": format_currency_brl(price_num) if price_num else (s.get('price') or ''),
                            "source": source,
                            "url": link,
                            "thumbnail": img_url,
                            "snippet": s.get('delivery', '') or f"Disponível em {source}"
                        })
            except Exception as e:
                logger.warning(f"Erro na busca shopping Serper: {e}")

            # Busca Orgânica Google Serper complementar
            try:
                search_resp = requests.post(
                    "https://google.serper.dev/search",
                    json={"q": f"{query_clean} preço ficha técnica mercado livre amazon", "gl": "br", "hl": "pt-br", "num": 6},
                    headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                    timeout=8
                )
                if search_resp.status_code == 200:
                    search_data = search_resp.json()
                    for org in search_data.get('organic', []):
                        title = org.get('title', '').strip()
                        link = org.get('link', '')
                        snippet = org.get('snippet', '').strip()

                        if snippet:
                            all_snippets.append(snippet)
                            extracted = cls._extract_prices_from_text(snippet)
                            if extracted.get('preco_novo'):
                                found_prices_new.append(extracted['preco_novo'])
                            if extracted.get('preco_usado'):
                                found_prices_used.append(extracted['preco_usado'])

                        # Identifica fonte a partir do domínio
                        source_label = "Web / Loja"
                        link_lower = link.lower()
                        if "mercadolivre.com" in link_lower:
                            source_label = "Mercado Livre"
                        elif "amazon.com" in link_lower:
                            source_label = "Amazon Brasil"
                        elif "kabum.com" in link_lower:
                            source_label = "KaBuM!"
                        elif "magazineluiza.com" in link_lower or "magalu" in link_lower:
                            source_label = "Magalu"
                        elif "shopee.com" in link_lower:
                            source_label = "Shopee"
                        elif "olx.com" in link_lower:
                            source_label = "OLX"

                        if link and link.startswith('http') and link not in reference_urls:
                            reference_urls.append(link)

                        # Adiciona como item se ainda tivermos poucos itens
                        if len(items) < 8 and title and link:
                            ext_p = cls._extract_prices_from_text(snippet)
                            p_val = ext_p.get('preco_novo') or ext_p.get('preco_usado')
                            items.append({
                                "title": title,
                                "price": p_val,
                                "price_formatted": format_currency_brl(p_val),
                                "source": source_label,
                                "url": link,
                                "thumbnail": "",
                                "snippet": snippet[:150]
                            })
            except Exception as e:
                logger.warning(f"Erro na busca orgânica Serper: {e}")

        # 2. Tavily API como complemento/fallback se Serper não retornou itens
        if len(items) == 0 and tavily_key:
            try:
                tav_data = cls._call_tavily(query_clean, tavily_key)
                if tav_data.get('preco_novo_estimado'):
                    found_prices_new.append(tav_data['preco_novo_estimado'])
                if tav_data.get('preco_usado_medio'):
                    found_prices_used.append(tav_data['preco_usado_medio'])
                for u in tav_data.get('urls_referencia', []):
                    if u not in reference_urls:
                        reference_urls.append(u)
            except Exception as e:
                logger.warning(f"Erro no fallback Tavily para busca de título: {e}")

        # 3. Fallback de links diretos se nenhum resultado online foi retornado
        if not reference_urls:
            encoded = urllib.parse.quote_plus(query_clean)
            ml_slug = urllib.parse.quote(query_clean.replace(' ', '-'))
            reference_urls = [
                f"https://lista.mercadolivre.com.br/{ml_slug}",
                f"https://www.amazon.com.br/s?k={encoded}",
                f"https://www.google.com/search?q={encoded}+preco+brasil"
            ]

        # 4. Cálculo e Consolidação da Sugestão Inteligente
        preco_novo_final: Optional[float] = None
        preco_usado_final: Optional[float] = None

        if found_prices_new:
            found_prices_new.sort()
            preco_novo_final = round(found_prices_new[len(found_prices_new)//2], 2)

        if found_prices_used:
            found_prices_used.sort()
            preco_usado_final = round(found_prices_used[len(found_prices_used)//2], 2)
        elif preco_novo_final:
            preco_usado_final = round(preco_novo_final * 0.60, 2)

        # Escolhe o melhor título limpo e padronizado
        suggested_title = query_clean
        if items and items[0].get('title'):
            first_title = items[0]['title']
            cleaned = re.sub(r'(?i)\b(frete gr[aá]tis|original|oferta|promo[cç][aã]o|envio r[aá]pido|pronta entrega|novo)\b', '', first_title)
            cleaned = re.sub(r'[\-\|\–]\s*$', '', cleaned).strip()
            if len(cleaned) >= 5 and len(cleaned) <= 80:
                suggested_title = cleaned

        categoria_slug = str(cls.infer_category(f"{query_clean} {suggested_title} {' '.join(all_snippets)}"))
        categoria_choices_dict = dict(Item.Categoria.choices)
        categoria_display = categoria_choices_dict.get(categoria_slug, "Outros")

        clean_ranked_urls = cls._filter_and_rank_urls(reference_urls, query_clean)[:4]

        # Coleta imagens válidas e únicas encontradas na pesquisa
        all_image_urls = []
        for it in items:
            t_url = it.get('thumbnail')
            if t_url and t_url.startswith('http') and t_url not in all_image_urls:
                all_image_urls.append(t_url)

        # Gera descrição estruturada com ficha técnica e transparência
        desc_lines = [
            f"📦 **Visão Geral**: {suggested_title}",
            "Item de excelente qualidade e desempenho comprovado no mercado.",
            "",
            "📋 **Ficha Técnica & Destaques**:",
            f"- **Produto / Modelo**: {suggested_title}",
            f"- **Categoria**: {categoria_display}",
        ]
        if preco_novo_final:
            desc_lines.append(f"- **Referência Novo no Mercado**: {format_currency_brl(preco_novo_final)}")
        if preco_usado_final:
            desc_lines.append(f"- **Preço Sugerido de Desapego**: {format_currency_brl(preco_usado_final)}")

        desc_lines.extend([
            "",
            "🔍 **Transparência Total & Estado Real**:",
            "- Produto em ótimo estado de conservação e funcionamento.",
            "- Revisado e pronto para uso imediato.",
            "",
            "🎁 **Itens Inclusos**:",
            "- Acompanha o produto conforme fotos e especificações originais.",
            "",
            "🚚 **Condições de Retirada & Envio**:",
            "- Retirada presencial ou envio com embalagem reforçada."
        ])
        suggested_description = "\n".join(desc_lines)

        suggestion = {
            "titulo": suggested_title,
            "preco_novo": preco_novo_final,
            "preco_novo_formatado": format_currency_brl(preco_novo_final),
            "preco_usado": preco_usado_final,
            "preco_usado_formatado": format_currency_brl(preco_usado_final),
            "categoria": categoria_slug,
            "categoria_display": str(categoria_display),
            "tipo_anuncio": Item.TipoAnuncio.VENDA,
            "tipo_anuncio_display": "Venda",
            "descricao": suggested_description,
            "images": all_image_urls[:6],
            "urls": clean_ranked_urls
        }

        return {
            "success": True,
            "query": query_clean,
            "total": len(items),
            "items": items[:6],
            "suggestion": suggestion
        }

    @classmethod
    def _fallback_market_data(cls, produto_query: str, visual_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        if visual_urls:
            urls = visual_urls[:5]
        else:
            encoded_query = urllib.parse.quote_plus(produto_query)
            ml_query = urllib.parse.quote(produto_query.replace(' ', '-'))
            urls = [
                f"https://lista.mercadolivre.com.br/{ml_query}",
                f"https://www.amazon.com.br/s?k={encoded_query}",
                f"https://www.google.com/search?q={encoded_query}+preco+brasil"
            ]
        return {
            "preco_novo_estimado": None,
            "preco_usado_medio": None,
            "urls_referencia": urls,
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
            "2. 📋 **Ficha Técnica & Especificações Exatas**: Liste as especificações técnicas oficiais e reais do modelo identificado (ex: para áudio/fones: tipo de driver, resposta de frequência, impedância, conector P2/P10/Bluetooth/USB, microfone integrado, isolamento acústico, peso; para instrumentos: madeiras, captação, trastes; para informática/eletrônicos: processador, memória, tela, conexões; para suportes/eletros/ferramentas: dimensões, materiais, capacidade de peso, compatibilidade, voltagem, potência).\n"
            "3. 🔍 **Transparência Total (Estado Real & Detalhes Visíveis)**: Detalhe de forma 100% honesta qualquer marca de uso, arranhão, desgaste ou detalhe apontado pela visão computacional ou pelo vendedor.\n"
            "4. 🎁 **Itens Inclusos**: Liste tudo o que acompanha o produto (cabos, adaptadores, capa, manuais, caixa).\n"
            "5. 🚚 **Condições de Retirada & Envio**: Informações práticas sobre retirada em mãos ou envio seguro.\n\n"
            "REGRAS DE CONTEÚDO IMPORTANTES:\n"
            "- NÃO inclua imagens em Markdown ![...](...) nem tags HTML <img> na descrição. As fotos do produto já são gerenciadas pela galeria do site. A descrição deve ser puramente textual (títulos, listas com marcadores, negrito e parágrafos).\n\n"
            "Retorne a resposta ESTRITAMENTE em formato JSON com o seguinte schema:\n"

            "{\n"
            '  "titulo": "Título objetivo e atrativo com marca, modelo e atributo principal (max 70 chars)",\n'
            '  "slug": "Slug amigável, simples, curto e limpo em minúsculas com hífens baseado no produto, marca e modelo (ex: \'fone-sennheiser-hd-400s\', \'suporte-tomate-mtg-164\', \'violao-yamaha-c40\')",\n'
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
            "REGRAS DE CONTEÚDO IMPORTANTES:\n"
            "- NÃO inclua imagens em Markdown ![...](...) nem tags HTML <img> na descrição. As fotos do produto são gerenciadas pela galeria do site. A descrição deve ser puramente textual (títulos, listas com marcadores, negrito e parágrafos).\n\n"
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
    1. Busca Visual Reversa (Google Lens / Google Vision)
    2. Visão Computacional Enriquecida
    3. Pesquisa de Mercado & Ficha Técnica
    4. Copywriting Técnico & Precificação
    5. Notificação
    """
    @classmethod
    def process_item(cls, item_id: int, use_serpapi: bool = False) -> Dict[str, Any]:
        try:
            item = Item.objects.get(pk=item_id)
        except Item.DoesNotExist:
            return {"success": False, "error": f"Item {item_id} não encontrado."}

        modo_txt = "Google Lens Profundo (SerpApi)" if use_serpapi else "Padrão Gratuito (Lens Nativo + Vision + Gemini)"
        logger.info(f"Iniciando pipeline de IA [{modo_txt}] para o Item ID {item_id}: {item.titulo}")

        # Passo 1: Busca Visual Reversa (Google Lens Nativo / SerpApi Lens se sob demanda)
        visual_result = VisualSearchService.search_by_image(item, use_serpapi=use_serpapi)
        if visual_result.get("success"):
            logger.info(f"Busca visual reversa ({visual_result.get('provider')}): '{visual_result.get('produto_identificado')}'")

        # Passo 2: Visão Computacional (alimentada com a dica visual identificada)
        vision_result = VisionService.analyze_item_images(item, visual_hint=visual_result)

        # Se a busca visual identificou marca/modelo específicos e a visão computacional veio genérica, mescla
        if visual_result.get("success"):
            if visual_result.get("marca") and (not vision_result.get("marca") or "gen" in vision_result.get("marca", "").lower()):
                vision_result["marca"] = visual_result["marca"]
            if visual_result.get("modelo") and (not vision_result.get("modelo") or vision_result.get("modelo", "").lower() in ["padrão", "padrao", "outros"]):
                vision_result["modelo"] = visual_result["modelo"]
            if visual_result.get("produto_identificado") and vision_result.get("produto_identificado", "").lower() in ["item avaliado", "item em análise", "produto em desapego", "suporte para celular"]:
                vision_result["produto_identificado"] = visual_result["produto_identificado"]

        # Passo 3: Construção da Query Otimizada e Pesquisa de Mercado
        search_query = MarketSearchService.build_search_query(vision_result, item.titulo, visual_hint=visual_result)
        logger.info(f"Query otimizada construída para busca de mercado: '{search_query}'")
        market_result = MarketSearchService.search_market_prices(
            search_query,
            visual_urls=visual_result.get("urls_diretas", [])
        )

        # Passo 4: Copywriting com Ficha Técnica Exata e Transparência Total
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
            raw_desc = copy_result['descricao']
            # Remove qualquer tag de imagem Markdown ![...](...) ou HTML <img...>
            clean_desc = re.sub(r'!\[.*?\]\(.*?\)', '', raw_desc)
            clean_desc = re.sub(r'<img[^>]*>', '', clean_desc)
            item.descricao_ia = clean_desc.strip()


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

        # Passo 5: Notificação
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
            "visual_data": visual_result,
            "vision_data": vision_result,
            "market_data": {
                "preco_novo_estimado": market_result.get("preco_novo_estimado"),
                "preco_usado_medio": market_result.get("preco_usado_medio"),
                "urls_count": len(market_result.get("urls_referencia", []))
            }
        }
