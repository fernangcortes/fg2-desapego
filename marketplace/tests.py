from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from core.models import Item, ConfiguracaoVendedor
from .formatters import (
    format_for_olx,
    format_for_mercadolivre,
    format_for_facebook,
    format_whatsapp_message
)

User = get_user_model()


class MarketplaceFormattersTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_superuser(
            username='staff_mkp',
            email='staff_mkp@test.com',
            password='password123'
        )
        self.config = ConfiguracaoVendedor.get_solo()
        self.config.nome_vendedor = "Vendedor Teste"
        self.config.whatsapp = "5511999991234"
        self.config.save()

        self.item = Item.objects.create(
            titulo="Microfone Shure SM58 Dinâmico",
            slug="microfone-shure-sm58-dinamico",
            descricao_ia="Microfone profissional para voz e estúdio.",
            preco_usado=650.00,
            preco_novo_referencia=1100.00,
            preco_aluguel=50.00,
            tipo_anuncio=Item.TipoAnuncio.AMBOS,
            categoria=Item.Categoria.INSTRUMENTOS,
            estado_conservacao=Item.EstadoConservacao.BOM,
            defeitos_visiveis="Pequeno desgaste na grade de proteção metálica",
            status=Item.Status.APROVADO
        )

    def test_format_whatsapp_message_exact_content(self):
        base_url = "https://desapego.meupessoal.com"
        wa_data = format_whatsapp_message(self.item, self.config, base_url)

        expected_msg = (
            "Olá, vi seu anúncio no site e tenho interesse no Microfone Shure SM58 Dinâmico "
            "pelo valor de R$ 650,00. Segue link: https://desapego.meupessoal.com/item/microfone-shure-sm58-dinamico/"
        )
        self.assertEqual(wa_data["mensagem"], expected_msg)
        self.assertIn("5511999991234", wa_data["whatsapp_url"])
        self.assertIn("Microfone", wa_data["whatsapp_url"])

    def test_format_for_olx(self):
        texto = format_for_olx(self.item, "https://desapego.com")
        self.assertIn("Microfone Shure SM58 Dinâmico", texto)
        self.assertIn("VALOR: R$ 650,00", texto)
        self.assertIn("Pequeno desgaste na grade de proteção metálica", texto)
        self.assertIn("DISPONÍVEL TAMBÉM PARA ALUGUEL: R$ 50,00", texto)
        # Garante ausência de caracteres crus markdown
        self.assertNotIn("**", texto)

    def test_format_for_mercadolivre(self):
        texto = format_for_mercadolivre(self.item, "https://desapego.com")
        self.assertIn("MICROFONE SHURE SM58 DINÂMICO", texto)
        self.assertIn("Condição: Bom estado", texto)
        self.assertIn("Preço: R$ 650,00", texto)

    def test_format_for_facebook(self):
        texto = format_for_facebook(self.item, "https://desapego.com")
        self.assertIn("DESAPEGO: Microfone Shure SM58 Dinâmico", texto)
        self.assertIn("R$ 650,00", texto)

    def test_export_views(self):
        # Sem login deve redirecionar
        resp = self.client.get(f'/marketplace/export/{self.item.id}/')
        self.assertEqual(resp.status_code, 302)

        # Logado como staff
        self.client.login(username='staff_mkp', password='password123')
        resp_modal = self.client.get(f'/marketplace/export/{self.item.id}/')
        self.assertEqual(resp_modal.status_code, 200)
        self.assertContains(resp_modal, "Copiar Descrição OLX")

        # Teste API
        resp_api = self.client.get(f'/marketplace/export/{self.item.id}/olx/')
        self.assertEqual(resp_api.status_code, 200)
        json_data = resp_api.json()
        self.assertEqual(json_data['platform'], 'olx')
        self.assertIn('VALOR:', json_data['text'])
