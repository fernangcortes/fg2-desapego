from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import Item, ImagemItem
from .services import (
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

    def test_build_search_query_fallback(self):
        vision_data = {
            "produto_identificado": "",
            "marca": "Genérica / Não identificada",
            "modelo": "Padrão",
        }
        query = MarketSearchService.build_search_query(vision_data, "Cadeira de Escritório Ergonômica")
        self.assertEqual(query, "Cadeira de Escritório Ergonômica")

    def test_filter_and_rank_urls_excludes_junk_and_includes_direct_search(self):
        raw_urls = [
            "https://www.techtudo.com.br/listas/2025/06/melhor-fone-over-ear-6-modelos-que-valem-cada-centavo-em-2025-edinfoeletro.ghtml",
            "https://www.amazon.com.br/gp/bestsellers/electronics/16244120011",
            "https://www.mercadolivre.com.br/blog/10-itens-mais-vendidos-em-fone-de-ouvido",
            "https://www.amazon.com.br/Fones-Ouvido/b?ie=UTF8&node=16244120011",
            "https://www.amazon.com.br/Sennheiser-Professional-Audio-400S-inteligente/dp/B07NFQ9FQQ",
            "https://www.mercadolivre.com.br/p/MLB1234567"
        ]
        query = "Sennheiser HD 400S"
        filtered = MarketSearchService._filter_and_rank_urls(raw_urls, query)

        # Não deve conter links de blogs ou bestsellers
        for url in filtered:
            self.assertNotIn("techtudo.com.br/listas", url)
            self.assertNotIn("bestsellers", url)
            self.assertNotIn("/blog/", url)
            self.assertNotIn("node=", url)

        # Deve conter páginas válidas do produto
        self.assertTrue(any("dp/B07NFQ9FQQ" in u for u in filtered))
        self.assertTrue(any("MLB1234567" in u for u in filtered))

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
        self.assertIn("Ficha Técnica", result["descricao"])
        self.assertIn("Transparência Total", result["descricao"])
        self.assertIn("Pequeno risco na lateral", result["descricao"])
        self.assertEqual(result["preco_usado"], 450.0)
        self.assertEqual(result["preco_novo"], 800.0)
        self.assertGreater(result["preco_aluguel"], 0)

    def test_ai_orchestrator_end_to_end(self):
        result = AIOrchestrator.process_item(self.item.id)
        self.assertTrue(result["success"])

        # Recarrega do banco
        self.item.refresh_from_db()
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
