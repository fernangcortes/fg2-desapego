import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import Item, ImagemItem
from .services import (
    VisualSearchService,
    VisionService,
    MarketSearchService,
    CopywritingService,
    NotificationService,
    AIOrchestrator
)

User = get_user_model()


@override_settings(AI_CONFIG={})
class AIEngineServicesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_superuser(
            username='staff_test',
            email='staff@test.com',
            password='password123'
        )
        self.dummy_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
            b'\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
            b'\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        )
        self.item = Item.objects.create(
            titulo="Violão Acústico Yamaha C40",
            status=Item.Status.RASCUNHO,
            defeitos_visiveis="Pequeno arranhão no tampo traseiro"
        )
        img_file = SimpleUploadedFile("violao.gif", self.dummy_gif, content_type="image/gif")
        ImagemItem.objects.create(item=self.item, imagem=img_file, ordem=0, principal=True)

    def test_visual_search_service_fallback(self):
        # Sem chaves de API, deve retornar fallback seguro
        result = VisualSearchService.search_by_image(self.item)
        self.assertFalse(result["success"])
        self.assertEqual(result["provider"], "none")
        self.assertEqual(result["urls_diretas"], [])

    @patch('requests.post')
    def test_visual_search_google_vision_web_detection(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "responses": [{
                "webDetection": {
                    "bestGuessLabels": [{"label": "suporte de mesa tomate mtg-164"}],
                    "webEntities": [
                        {"description": "Tomate MTG-164", "score": 0.95},
                        {"description": "Suporte articulado", "score": 0.8}
                    ],
                    "pagesWithMatchingImages": [
                        {"url": "https://www.lojatomate.com.br/suporte-de-mesa-mtg-164"},
                        {"url": "https://www.mercadolivre.com.br/suporte-articulado-tomate-mtg164"}
                    ]
                }
            }]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        img_path = self.item.imagens.first().imagem.path
        result = VisualSearchService._call_google_vision_web_detection(img_path, "fake_key")
        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "google_vision_web_detection")
        self.assertEqual(result["produto_identificado"], "suporte de mesa tomate mtg-164")
        self.assertIn("https://www.lojatomate.com.br/suporte-de-mesa-mtg-164", result["urls_diretas"])

    @patch('requests.post')
    @patch('requests.get')
    def test_visual_search_serpapi_google_lens(self, mock_get, mock_post):
        # Mock upload de imagem
        upload_resp = MagicMock()
        upload_resp.json.return_value = {"image_id": "img_12345"}
        upload_resp.raise_for_status = MagicMock()
        mock_post.return_value = upload_resp

        # Mock resultado Google Lens
        lens_resp = MagicMock()
        lens_resp.json.return_value = {
            "visual_matches": [
                {
                    "title": "Suporte Articulado Tomate MTG-164",
                    "link": "https://www.mercadolivre.com.br/p/MLB99999",
                    "source": "Mercado Livre"
                }
            ]
        }
        lens_resp.raise_for_status = MagicMock()
        mock_get.return_value = lens_resp

        img_path = self.item.imagens.first().imagem.path
        result = VisualSearchService._call_serpapi_google_lens(img_path, "fake_serpapi_key")
        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "serpapi_google_lens")
        self.assertEqual(result["produto_identificado"], "Suporte Articulado Tomate MTG-164")
        self.assertIn("https://www.mercadolivre.com.br/p/MLB99999", result["urls_diretas"])

    def test_vision_service_fallback(self):
        # Sem API keys configuradas, deve retornar dados fallback coerentes
        result = VisionService.analyze_item_images(self.item)
        self.assertIn("produto_identificado", result)
        self.assertIn("defeitos_visiveis", result)
        self.assertEqual(result["defeitos_visiveis"], "Pequeno arranhão no tampo traseiro")

    @patch('requests.post')
    def test_vision_service_gemini(self, mock_post):
        mock_resp = MagicMock()
        json_data = '{"produto_identificado": "Violão Yamaha C40", "marca": "Yamaha", "modelo": "C40", "categoria_sugerida": "instrumentos", "estado_conservacao": "bom", "defeitos_visiveis": "Leves marcas no verniz", "acessorios_visiveis": "Capa acolchoada", "especificacoes_visiveis": "Cordas de nylon"}'
        mock_resp.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{
                        'text': json_data
                    }]
                }
            }]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = VisionService._call_gemini_vision(self.item.imagens.all(), "fake_key", self.item)
        self.assertEqual(result["produto_identificado"], "Violão Yamaha C40")
        self.assertEqual(result["categoria_sugerida"], "instrumentos")
        self.assertEqual(result["defeitos_visiveis"], "Leves marcas no verniz")

    def test_build_search_query_sennheiser(self):
        vision_data = {
            "produto_identificado": "Fone de Ouvido Over-Ear com Microfone",
            "marca": "Sennheiser",
            "modelo": "HD 400S",
        }
        query = MarketSearchService.build_search_query(vision_data, "Item em análise (13/08 às 22:00)")
        self.assertIn("Sennheiser", query)
        self.assertIn("HD 400S", query)
        self.assertIn("Fone de Ouvido", query)
        self.assertNotIn("Item em análise", query)

    def test_build_search_query_with_visual_hint(self):
        vision_data = {
            "produto_identificado": "Suporte para Celular",
            "marca": "Genérica",
            "modelo": "Padrão",
        }
        visual_hint = {
            "produto_identificado": "Suporte de Mesa Tomate MTG-164",
            "marca": "Tomate",
            "modelo": "MTG-164"
        }
        query = MarketSearchService.build_search_query(vision_data, visual_hint=visual_hint)
        self.assertIn("Tomate", query)
        self.assertIn("MTG-164", query)

    def test_build_search_query_fallback(self):
        vision_data = {
            "produto_identificado": "",
            "marca": "Genérica / Não identificada",
            "modelo": "Padrão",
        }
        query = MarketSearchService.build_search_query(vision_data, "Cadeira de Escritório Ergonômica")
        self.assertEqual(query, "Cadeira de Escritório Ergonômica")

    def test_filter_and_rank_urls_with_visual_urls(self):
        raw_urls = [
            "https://www.techtudo.com.br/listas/2025/06/melhor-fone.ghtml",
            "https://www.amazon.com.br/gp/bestsellers/electronics/16244120011",
            "https://www.mercadolivre.com.br/p/MLB1234567"
        ]
        visual_urls = [
            "https://www.lojatomate.com.br/suporte-mtg-164",
            "https://www.amazon.com.br/dp/B07NFQ9FQQ"
        ]
        query = "Tomate MTG-164"
        filtered = MarketSearchService._filter_and_rank_urls(raw_urls, query, visual_urls=visual_urls)

        # URLs visuais devem estar no topo
        self.assertEqual(filtered[0], "https://www.lojatomate.com.br/suporte-mtg-164")
        self.assertEqual(filtered[1], "https://www.amazon.com.br/dp/B07NFQ9FQQ")

        # Não deve conter links de blogs ou bestsellers
        for url in filtered:
            self.assertNotIn("techtudo.com.br/listas", url)
            self.assertNotIn("bestsellers", url)

    def test_market_search_price_extraction(self):
        sample_text = "Yamaha C40 Violão Clássico Novo por R$ 850,00 na Amazon e usado por R$ 480,00 na OLX."
        prices = MarketSearchService._extract_prices_from_text(sample_text)
        self.assertEqual(prices["preco_novo"], 850.0)
        self.assertEqual(prices["preco_usado"], 480.0)

    def test_copywriting_fallback(self):
        vision_data = {
            "produto_identificado": "Violão Clássico Yamaha C40",
            "marca": "Yamaha",
            "modelo": "C40",
            "categoria_sugerida": "instrumentos",
            "estado_conservacao": "bom",
            "defeitos_visiveis": "Pequeno risco na lateral",
            "acessorios_visiveis": "Capa simples",
            "especificacoes_visiveis": "Madeira de abeto, escala em pau-rosa, cordas de nylon"
        }
        market_data = {
            "preco_novo_estimado": 800.0,
            "preco_usado_medio": 450.0,
            "urls_referencia": ["https://mercadolivre.com.br/yamaha-c40"]
        }

        result = CopywritingService._fallback_copywriting(vision_data, market_data, "Cordas novas")
        self.assertIn("Yamaha", result["titulo"])
        self.assertIn("slug", result)
        self.assertEqual(result["slug"], "violao-classico-yamaha-c40")
        self.assertIn("Ficha Técnica", result["descricao"])
        self.assertIn("Transparência Total", result["descricao"])
        self.assertIn("Pequeno risco na lateral", result["descricao"])
        self.assertEqual(result["preco_usado"], 450.0)
        self.assertEqual(result["preco_novo"], 800.0)
        self.assertGreater(result["preco_aluguel"], 0)

    def test_ai_orchestrator_end_to_end(self):
        # Configura item com título provisório de upload rápido
        self.item.titulo = "Item em análise (13/08 às 21:37)"
        self.item.slug = "item-em-analise-1308-as-2137"
        self.item.save()

        result = AIOrchestrator.process_item(self.item.id)
        self.assertTrue(result["success"])
        self.assertIn("slug", result)
        self.assertIn("visual_data", result)

        # Recarrega do banco
        self.item.refresh_from_db()
        self.assertFalse(self.item.slug.startswith("item-em-analise"))
        self.assertEqual(result["slug"], self.item.slug)
        self.assertTrue(bool(self.item.descricao_ia))
        self.assertIn("Ficha Técnica", self.item.descricao_ia)
        self.assertIsNotNone(self.item.preco_usado)
        self.assertIsNotNone(self.item.preco_novo_referencia)
        self.assertIsNotNone(self.item.preco_aluguel)
        self.assertTrue(isinstance(self.item.urls_referencia, list))

    def test_process_item_view_staff_required(self):
        # Acesso anônimo deve redirecionar para login
        response = self.client.get(f'/ai/process/{self.item.id}/')
        self.assertEqual(response.status_code, 302)

        # Acesso staff logado
        self.client.login(username='staff_test', password='password123')
        response_auth = self.client.get(f'/ai/process/{self.item.id}/', HTTP_ACCEPT='application/json')
        self.assertEqual(response_auth.status_code, 200)
        data = response_auth.json()
        self.assertTrue(data.get('success'))
        self.assertIn('slug', data)

    def test_infer_category(self):
        self.assertEqual(MarketSearchService.infer_category("Violão Yamaha C40"), Item.Categoria.INSTRUMENTOS)
        self.assertEqual(MarketSearchService.infer_category("Guitarra Fender Stratocaster"), Item.Categoria.INSTRUMENTOS)
        self.assertEqual(MarketSearchService.infer_category("Smartphone iPhone 13 Pro 128GB"), Item.Categoria.ELETRONICOS)
        self.assertEqual(MarketSearchService.infer_category("Fone Bluetooth JBL Tune 510BT"), Item.Categoria.ELETRONICOS)
        self.assertEqual(MarketSearchService.infer_category("Furadeira de Impacto Bosch 650W"), Item.Categoria.FERRAMENTAS)
        self.assertEqual(MarketSearchService.infer_category("Cafeteira Nespresso Essenza Mini"), Item.Categoria.ELETRODOMESTICOS)
        self.assertEqual(MarketSearchService.infer_category("Cadeira Gamer ThunderX3"), Item.Categoria.MOVEIS)
        self.assertEqual(MarketSearchService.infer_category("Tênis Nike Air Max 90"), Item.Categoria.VESTUARIO)
        self.assertEqual(MarketSearchService.infer_category("Bicicleta Caloi Aro 29"), Item.Categoria.ESPORTES)
        self.assertEqual(MarketSearchService.infer_category("Box Harry Potter Edição Especial"), Item.Categoria.LIVROS)

    def test_search_internet_products_empty(self):
        res = MarketSearchService.search_internet_products("")
        self.assertFalse(res["success"])
        self.assertEqual(res["total"], 0)

        res_short = MarketSearchService.search_internet_products("a")
        self.assertFalse(res_short["success"])
        self.assertEqual(res_short["total"], 0)

    @patch('requests.post')
    def test_search_internet_products_mock(self, mock_post):
        # Mock do shopping e organic
        mock_resp_shop = MagicMock()
        mock_resp_shop.status_code = 200
        mock_resp_shop.json.return_value = {
            "shopping": [
                {
                    "title": "Violão Acústico Yamaha C40MII Nylon",
                    "price": "R$ 799,00",
                    "source": "Mercado Livre",
                    "link": "https://www.mercadolivre.com.br/violao-yamaha-c40",
                    "imageUrl": "https://http2.mlstatic.com/img.jpg"
                },
                {
                    "title": "Violão Yamaha C40 II Clássico",
                    "price": "R$ 899,00",
                    "source": "Amazon Brasil",
                    "link": "https://www.amazon.com.br/dp/B0002F58TG",
                    "imageUrl": "https://amazon.com/img.jpg"
                }
            ]
        }

        mock_post.return_value = mock_resp_shop

        with override_settings(AI_CONFIG={'SERPER_API_KEY': 'fake_serper_key'}):
            res = MarketSearchService.search_internet_products("Violao Yamaha C40")
            self.assertTrue(res["success"])
            self.assertGreaterEqual(res["total"], 2)
            self.assertEqual(res["suggestion"]["categoria"], Item.Categoria.INSTRUMENTOS)
            self.assertIsNotNone(res["suggestion"]["preco_novo"])
            self.assertIsNotNone(res["suggestion"]["preco_usado"])
            self.assertTrue(len(res["suggestion"]["urls"]) > 0)

    def test_search_internet_products_view(self):
        # Sem login deve redirecionar (staff_member_required)
        resp_unauth = self.client.get('/ai/search-title/?q=Violao')
        self.assertEqual(resp_unauth.status_code, 302)

        # Logado como staff
        self.client.login(username='staff_test', password='password123')

        # Query vazia
        resp_empty = self.client.get('/ai/search-title/?q=')
        self.assertEqual(resp_empty.status_code, 200)
        data_empty = resp_empty.json()
        self.assertFalse(data_empty["success"])

        # Query válida com fallback
        resp = self.client.get('/ai/search-title/?q=Violao%20Yamaha%20C40')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["query"], "Violao Yamaha C40")
        self.assertIn("suggestion", data)
        self.assertIn("categoria", data["suggestion"])
        self.assertIn("images", data["suggestion"])
        self.assertIn("descricao", data["suggestion"])
        self.assertIn("tipo_anuncio", data["suggestion"])

    @patch('requests.get')
    def test_proxy_image_view(self, mock_get):
        # Sem login deve redirecionar (staff_member_required)
        resp_unauth = self.client.get('/ai/proxy-image/?url=https://example.com/foto.gif')
        self.assertEqual(resp_unauth.status_code, 302)

        # Logado como staff
        self.client.login(username='staff_test', password='password123')

        # Teste URL vazia / inválida
        resp_invalid = self.client.get('/ai/proxy-image/?url=')
        self.assertEqual(resp_invalid.status_code, 400)

        # Teste download bem-sucedido
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = self.dummy_gif
        mock_resp.headers = {'Content-Type': 'image/gif'}
        mock_get.return_value = mock_resp

        resp_ok = self.client.get('/ai/proxy-image/?url=https://example.com/foto.gif')
        self.assertEqual(resp_ok.status_code, 200)
        self.assertEqual(resp_ok['Content-Type'], 'image/gif')
        self.assertEqual(resp_ok.content, self.dummy_gif)

    @patch('requests.get')
    def test_import_web_images_view(self, mock_get):
        # Sem login deve redirecionar (staff_member_required)
        resp_unauth = self.client.post(
            '/ai/import-web-images/',
            data='{"item_id": 1, "images": []}',
            content_type='application/json'
        )
        self.assertEqual(resp_unauth.status_code, 302)

        # Logado como staff
        self.client.login(username='staff_test', password='password123')

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = self.dummy_gif
        mock_resp.headers = {'Content-Type': 'image/gif'}
        mock_get.return_value = mock_resp

        initial_count = self.item.imagens.count()

        resp = self.client.post(
            '/ai/import-web-images/',
            data=json.dumps({
                "item_id": self.item.id,
                "images": ["https://example.com/foto1.gif", "https://example.com/foto2.gif"]
            }),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("imported"), 2)
        self.assertEqual(self.item.imagens.count(), initial_count + 2)


