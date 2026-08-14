import os
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from .models import Item, ImagemItem, ConfiguracaoVendedor

User = get_user_model()


class HubDesapegoCoreTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='password123'
        )
        self.config = ConfiguracaoVendedor.get_solo()
        self.config.nome_vendedor = "Loja Teste"
        self.config.whatsapp = "5511999998888"
        self.config.save()

        # Dummy GIF
        self.dummy_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
            b'\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
            b'\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        )

    def test_configuracao_vendedor_singleton(self):
        config1 = ConfiguracaoVendedor.get_solo()
        config2 = ConfiguracaoVendedor.get_solo()
        self.assertEqual(config1.pk, config2.pk)
        self.assertEqual(ConfiguracaoVendedor.objects.count(), 1)

    def test_item_slug_generation(self):
        item1 = Item.objects.create(
            titulo="Câmera Sony A6400 4K",
            preco_usado=4500.00,
            status=Item.Status.APROVADO
        )
        self.assertEqual(item1.slug, "camera-sony-a6400-4k")

        item2 = Item.objects.create(
            titulo="Câmera Sony A6400 4K",
            preco_usado=4200.00,
            status=Item.Status.RASCUNHO
        )
        self.assertEqual(item2.slug, "camera-sony-a6400-4k-1")

    def test_item_provisional_slug_auto_update_on_save(self):
        # Cria item com título provisório de upload rápido
        item = Item.objects.create(
            titulo="Item em análise (13/08 às 21:37)",
            preco_usado=350.00,
            status=Item.Status.RASCUNHO
        )
        self.assertTrue(item.slug.startswith("item-em-analise"))

        # Atualiza título para um produto real e salva
        item.titulo = "Fone Sennheiser HD 400S"
        item.save()
        self.assertEqual(item.slug, "fone-sennheiser-hd-400s")

    def test_generate_unique_slug_custom_text(self):
        item = Item.objects.create(
            titulo="Produto Genérico",
            preco_usado=100.00
        )
        custom_slug = item.generate_unique_slug("sennheiser hd-400s p2")
        self.assertEqual(custom_slug, "sennheiser-hd-400s-p2")

    def test_item_descricao_efetiva(self):
        item = Item.objects.create(
            titulo="Monitor Dell 27 4K",
            descricao_ia="Excelente monitor 4K profissional.",
            descricao_manual=""
        )
        self.assertEqual(item.descricao_efetiva, "Excelente monitor 4K profissional.")

        item.descricao_manual = "Acompanha cabo HDMI e suporte ergonômico."
        item.save()
        self.assertEqual(item.descricao_efetiva, "Acompanha cabo HDMI e suporte ergonômico.")

    def test_item_imagens_and_admin_view(self):
        item = Item.objects.create(
            titulo="Notebook ThinkPad X1 Carbon",
            preco_usado=5800.00,
            status=Item.Status.APROVADO
        )

        img_file1 = SimpleUploadedFile("foto1.gif", self.dummy_gif, content_type="image/gif")
        img_file2 = SimpleUploadedFile("foto2.gif", self.dummy_gif, content_type="image/gif")

        img1 = ImagemItem.objects.create(item=item, imagem=img_file1, ordem=1, principal=False)
        img2 = ImagemItem.objects.create(item=item, imagem=img_file2, ordem=0, principal=True)

        self.assertEqual(item.imagem_principal, img2)
        self.assertEqual(item.imagens.count(), 2)

        self.client.login(username='admin_test', password='password123')
        response = self.client.get(f'/admin/core/item/{item.pk}/change/')
        self.assertEqual(response.status_code, 200)

        response_list = self.client.get('/admin/core/item/')
        self.assertEqual(response_list.status_code, 200)
        self.assertContains(response_list, "Notebook ThinkPad X1 Carbon")

    def test_home_page_renders_approved_items(self):
        Item.objects.create(
            titulo="Bicicleta Speed Caloi",
            preco_usado=1200.00,
            status=Item.Status.APROVADO
        )
        Item.objects.create(
            titulo="Item em Rascunho",
            preco_usado=100.00,
            status=Item.Status.RASCUNHO
        )

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bicicleta Speed Caloi")
        self.assertNotContains(response, "Item em Rascunho")

    # --- Testes da FASE 2: PWA e Upload Rápido ---

    def test_pwa_static_files_exist(self):
        manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
        sw_path = os.path.join(settings.BASE_DIR, 'static', 'service-worker.js')
        icon_path = os.path.join(settings.BASE_DIR, 'static', 'icons', 'icon-192.png')

        self.assertTrue(os.path.exists(manifest_path), "manifest.json não encontrado em static/")
        self.assertTrue(os.path.exists(sw_path), "service-worker.js não encontrado em static/")
        self.assertTrue(os.path.exists(icon_path), "icon-192.png não encontrado em static/icons/")

    def test_upload_rapido_get(self):
        response = self.client.get('/upload/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload Rápido de Item")
        self.assertContains(response, "Tirar Foto")
        self.assertContains(response, "Galeria")

    def test_upload_rapido_post_success(self):
        foto1 = SimpleUploadedFile("furadeira1.gif", self.dummy_gif, content_type="image/gif")
        foto2 = SimpleUploadedFile("furadeira2.gif", self.dummy_gif, content_type="image/gif")

        response = self.client.post('/upload/', {
            'titulo_provisorio': 'Furadeira de Impacto Bosch GSB 550',
            'categoria': Item.Categoria.FERRAMENTAS,
            'tipo_anuncio': Item.TipoAnuncio.VENDA,
            'observacoes': 'Acompanha maleta e 4 brocas.',
            'capa_index': '1', # selecionando a foto 2 como capa
            'imagens': [foto1, foto2]
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rascunho Salvo!")
        self.assertContains(response, "Furadeira de Impacto Bosch GSB 550")

        # Verifica criação no banco de dados
        item = Item.objects.filter(titulo='Furadeira de Impacto Bosch GSB 550').first()
        self.assertIsNotNone(item)
        self.assertEqual(item.status, Item.Status.RASCUNHO)
        self.assertEqual(item.categoria, Item.Categoria.FERRAMENTAS)
        self.assertEqual(item.defeitos_visiveis, 'Acompanha maleta e 4 brocas.')
        self.assertEqual(item.imagens.count(), 2)
        self.assertTrue(item.imagens.filter(ordem=1, principal=True).exists())

    def test_upload_rapido_post_without_images(self):
        response = self.client.post('/upload/', {
            'titulo_provisorio': 'Item sem foto',
            'imagens': []
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Por favor, selecione ou tire pelo menos uma foto")
        self.assertEqual(Item.objects.filter(titulo='Item sem foto').count(), 0)

    # --- Testes da FASE 4: Vitrine Pública e Detalhes ---

    def test_home_filtering_and_search(self):
        item_venda = Item.objects.create(
            titulo="Mesa de Jantar Madeira Maciça",
            preco_usado=900.00,
            tipo_anuncio=Item.TipoAnuncio.VENDA,
            categoria=Item.Categoria.MOVEIS,
            status=Item.Status.APROVADO
        )
        item_aluguel = Item.objects.create(
            titulo="Projetor Epson Full HD",
            preco_aluguel=150.00,
            tipo_anuncio=Item.TipoAnuncio.ALUGUEL,
            categoria=Item.Categoria.ELETRONICOS,
            status=Item.Status.APROVADO
        )

        # Filtro tipo venda
        resp_venda = self.client.get('/?tipo=venda')
        self.assertContains(resp_venda, "Mesa de Jantar Madeira Maciça")
        self.assertNotContains(resp_venda, "Projetor Epson Full HD")

        # Filtro tipo aluguel
        resp_aluguel = self.client.get('/?tipo=aluguel')
        self.assertContains(resp_aluguel, "Projetor Epson Full HD")
        self.assertNotContains(resp_aluguel, "Mesa de Jantar Madeira Maciça")

        # Filtro busca
        resp_busca = self.client.get('/?q=Epson')
        self.assertContains(resp_busca, "Projetor Epson Full HD")
        self.assertNotContains(resp_busca, "Mesa de Jantar")

    def test_item_detail_view(self):
        item = Item.objects.create(
            titulo="Violão Takamine Japonês",
            slug="violao-takamine-japones",
            preco_usado=3500.00,
            preco_novo_referencia=6000.00,
            defeitos_visiveis="Pequena marca no headstock",
            status=Item.Status.APROVADO
        )

        resp = self.client.get(f'/item/{item.slug}/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Violão Takamine Japonês")
        self.assertContains(resp, "R$ 3.500,00")
        self.assertContains(resp, "Pequena marca no headstock")
        self.assertContains(resp, "Tenho Interesse (Chamar no WhatsApp)")

    def test_item_detail_draft_visibility(self):
        draft_item = Item.objects.create(
            titulo="Item Secreto em Rascunho",
            slug="item-secreto-em-rascunho",
            status=Item.Status.RASCUNHO
        )

        # Anônimo recebe 404
        resp_anon = self.client.get(f'/item/{draft_item.slug}/')
        self.assertEqual(resp_anon.status_code, 404)

        # Staff logado consegue visualizar
        self.client.login(username='admin_test', password='password123')
        resp_staff = self.client.get(f'/item/{draft_item.slug}/')
        self.assertEqual(resp_staff.status_code, 200)
        self.assertContains(resp_staff, "Item Secreto em Rascunho")

    def test_quick_delete_anonymous_redirect(self):
        item = Item.objects.create(
            titulo="Item para Deletar Anon",
            preco_usado=100.00
        )
        resp = self.client.post(f'/item/{item.pk}/quick-delete/')
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Item.objects.filter(pk=item.pk).exists())

    def test_quick_delete_staff_ajax_success(self):
        item = Item.objects.create(
            titulo="Item para Deletar Staff",
            preco_usado=250.00
        )
        img_file = SimpleUploadedFile("foto_del.gif", self.dummy_gif, content_type="image/gif")
        ImagemItem.objects.create(item=item, imagem=img_file)

        self.client.login(username='admin_test', password='password123')
        resp = self.client.post(
            f'/item/{item.pk}/quick-delete/',
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        json_data = resp.json()
        self.assertTrue(json_data.get('success'))
        self.assertEqual(json_data.get('item_id'), item.pk)
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())
        self.assertEqual(ImagemItem.objects.filter(item_id=item.pk).count(), 0)

    def test_quick_delete_staff_redirect_success(self):
        item = Item.objects.create(
            titulo="Item Delete Normal",
            preco_usado=150.00
        )
        self.client.login(username='admin_test', password='password123')
        resp = self.client.post(f'/item/{item.pk}/quick-delete/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/admin/core/item/')
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())

    def test_quick_delete_get_not_allowed(self):
        item = Item.objects.create(
            titulo="Item Delete GET",
            preco_usado=50.00
        )
        self.client.login(username='admin_test', password='password123')
        resp = self.client.get(f'/item/{item.pk}/quick-delete/')
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Item.objects.filter(pk=item.pk).exists())

    def test_admin_changelist_contains_subtle_actions(self):
        item = Item.objects.create(
            titulo="Cadeira Ergonômica Top",
            preco_usado=890.00
        )
        self.client.login(username='admin_test', password='password123')
        resp = self.client.get('/admin/core/item/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "admin-subtle-actions")
        self.assertContains(resp, "admin-delete-action-btn")
        self.assertContains(resp, "admin_subtle_actions.js")
        self.assertContains(resp, "admin_subtle_actions.css")
        self.assertContains(resp, f'data-item-id="{item.pk}"')

    def test_markdown_extras_render_markdown(self):
        from core.templatetags.markdown_extras import render_markdown
        sample = (
            "## 📦 **Visão Geral**\n"
            "Fone de ouvido Sennheiser.\n\n"
            "## 📋 **Ficha Técnica & Especificações**\n"
            "• Driver: 40mm\n"
            "• Impedância: 18 Ohms\n\n"
            "💬 *Fique à vontade para perguntar!*"
        )
        html = render_markdown(sample)
        self.assertIn("<h2", html)
        self.assertIn("📦", html)
        self.assertIn("Visão Geral", html)
        self.assertNotIn("##", html)
        self.assertIn("<ul>", html)
        self.assertIn("<li>Driver: 40mm</li>", html)
        self.assertIn("<em>Fique à vontade para perguntar!</em>", html)

    def test_markdown_extras_strip_markdown(self):
        from core.templatetags.markdown_extras import strip_markdown
        sample = (
            "## 📦 **Visão Geral**\n"
            "Violão Yamaha C40.\n\n"
            "## 📋 **Ficha Técnica:**\n"
            "• Marca: Yamaha\n"
            "• Modelo: C40"
        )
        plain = strip_markdown(sample)
        self.assertNotIn("##", plain)
        self.assertNotIn("**", plain)
        self.assertIn("📦 Visão Geral Violão Yamaha C40. 📋 Ficha Técnica: Marca: Yamaha Modelo: C40", plain)

    def test_item_descricao_markdown_properties(self):
        item = Item.objects.create(
            titulo="Fone Bluetooth Anker",
            descricao_ia="## 📦 **Visão Geral**\nFone com cancelamento ativo.",
            status=Item.Status.APROVADO
        )
        self.assertIn("<h2", item.descricao_efetiva_html)
        self.assertNotIn("##", item.descricao_efetiva_html)
        self.assertIn("📦 Visão Geral Fone com cancelamento ativo.", item.descricao_efetiva_texto_puro)

    def test_item_detail_view_renders_formatted_markdown(self):
        item = Item.objects.create(
            titulo="Violão Acústico Eagle",
            descricao_ia="## 📦 **Visão Geral**\nViolão profissional com excelente afinação.\n\n## 📋 **Ficha Técnica**\n• Tampo: Spruce",
            status=Item.Status.APROVADO
        )
        resp = self.client.get(f'/item/{item.slug}/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "prose-desapego")
        self.assertContains(resp, "<h2")
        self.assertContains(resp, "<li>Tampo: Spruce</li>")
        # Ensure raw markdown headers are not displayed as literal text
        self.assertNotContains(resp, "## 📦 **Visão Geral**")

    def test_markdown_extras_strips_images(self):
        from core.templatetags.markdown_extras import render_markdown, strip_markdown
        sample = (
            "## 📦 **Visão Geral**\n"
            "Fone Sennheiser HD 400S.\n\n"
            "![Sennheiser HD 400S](https://m.media-amazon.com/images/I/41Xy6k+5Z+L._AC_SL1500_.jpg)\n"
            '<img src="https://img.com/test.png" alt="Test">'
        )
        html = render_markdown(sample)
        self.assertNotIn("<img", html)
        self.assertNotIn("media-amazon.com", html)
        self.assertIn("Fone Sennheiser HD 400S", html)

        plain = strip_markdown(sample)
        self.assertNotIn("media-amazon.com", plain)
        self.assertNotIn("<img", plain)
        self.assertNotIn("![", plain)




