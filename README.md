# 🏷️ Hub de Desapego Inteligente

Sistema pessoal e moderno para gerenciamento, precificação por Inteligência Artificial e venda/aluguel de centenas de itens usados por um casal.

Construído com **Python 3.12/3.14**, **Django 5.1**, **SQLite**, **TailwindCSS**, **HTMX**, **PWA (Progressive Web App)** e arquitetura de IA (*Chain of Thought*).

---

## ✨ Principais Funcionalidades

1. **📱 PWA Mobile com Câmera Nativa (`/upload/`)**:
   - Interface mobile-first otimizada para tirar fotos sequenciais de produtos com a câmera traseira do smartphone.
   - Prévia instantânea de fotos, remoção individual de imagens e seleção visual da foto de capa.
   - Salvamento automático de rascunhos com suporte a anotações rápidas de avarias.

2. **🧠 Pipeline Inteligente de IA (`ai_engine`)**:
   - **Visão Computacional (Google Gemini 3.7 Flash):** Identifica produto, marca, modelo e realiza detecção rigorosa de **marcas de uso, arranhões e defeitos visíveis**.
   - **Pesquisa de Mercado em Tempo Real (Tavily Search API):** Coleta preços e links de referência de itens novos (Amazon, Mercado Livre, Kabum) e usados (OLX, Enjoei).
   - **Copywriting Transparente (DeepSeek v4 API):** Redação persuasiva focada em **100% de honestidade**, apontando detalhes reais e sugerindo preços justos de venda e de aluguel.
   - **Notificações:** Alerta no Telegram quando novos itens estão prontos para aprovação.

3. **🛍️ Vitrine Pública Responsiva (`/`)**:
   - Exibição de itens aprovados com abas dinâmicas para *Todos*, *🏷️ Venda* e *🔄 Aluguel*.
   - Filtros por categoria em carrossel e busca instantânea por produto/marca.
   - Comparativo de economia real em relação ao produto novo nas lojas.

4. **🔍 Página de Detalhes com Transparência Total (`/item/<slug>/`)**:
   - Galeria interativa de fotos em alta resolução.
   - Box destacado exibindo com clareza qualquer marca de uso ou defeito identificado.
   - **Botão Inteligente de Contato ("Tenho Interesse"):** Abre o WhatsApp do vendedor com mensagem oficial pré-formatada:
     ```text
     "Olá, vi seu anúncio no site e tenho interesse no [Produto] pelo valor de [Preço]. Segue link: [Link]"
     ```
   - Botões diretos para Telegram, E-mail e cópia de chave PIX em 1 clique.

5. **📋 Exportador para Marketplaces (`marketplace`)**:
   - Botões e modal no Admin para copiar a descrição formatada em 1 clique para:
     - **OLX:** Texto puro, sem markdown quebrado, tópicos claros com emojis.
     - **Mercado Livre:** Formatação estruturada profissional com especificações.
     - **Facebook Marketplace:** Texto direto e atraente para grupos locais.

---

## 🛠️ Stack Tecnológica

| Componente | Tecnologia |
| :--- | :--- |
| **Linguagem & Backend** | Python 3.12 / 3.14 com Django 5.1.x |
| **Banco de Dados** | SQLite (desenvolvimento e produção em VPS) |
| **Frontend** | Django Templates + TailwindCSS (CDN) + HTMX |
| **Mobile** | PWA (Progressive Web App com `manifest.json` e `service-worker.js`) |
| **Visão Computacional** | Google Gemini 3.7 Flash (com fallback 3.6/3.5) |
| **Pesquisa de Mercado** | Tavily Search API / Serper API |
| **Copywriting** | DeepSeek API (`deepseek-chat` / v4) |
| **Hospedagem & Deploy** | Google Cloud (Compute Engine Always Free) / Gunicorn + Nginx + Systemd |

---

## 🚀 Como Executar Localmente

### 1. Clonar o repositório e criar o ambiente virtual
```bash
# Clone o repositório
git clone https://github.com/fernangcortes/fg2-desapego.git
cd fg2-desapego

# Crie e ative o ambiente virtual
python -m venv venv

# No Windows (PowerShell):
.\venv\Scripts\activate

# No Linux/Mac:
source venv/bin/activate
```

### 2. Instalar as dependências
```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente
Copie o arquivo de exemplo:
```bash
cp .env.example .env
```

### 4. Executar migrações e criar superusuário
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Iniciar o servidor de desenvolvimento
```bash
python manage.py runserver 0.0.0.0:8000
```

- 🏠 **Vitrine Pública:** [http://localhost:8000/](http://localhost:8000/)
- 📸 **Upload Rápido Mobile:** [http://localhost:8000/upload/](http://localhost:8000/upload/)
- ⚙️ **Painel Administrativo:** [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

## 🧪 Execução de Testes Automatizados

O projeto possui cobertura completa de testes unitários e de integração (23 testes automatizados):

```bash
python manage.py test
```

---

## 🔑 Guia de Chaves de API

Para ativar a inteligência artificial completa, adicione as chaves no arquivo `.env`:

| Serviço | Função | Onde Obter |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Visão Computacional (Fotos e Defeitos) | [Google AI Studio](https://aistudio.google.com/) *(Gratuito)* |
| `GROQ_API_KEY` | Modelos Alternativos LLM | [Groq Console](https://console.groq.com/) *(Gratuito)* |
| `TAVILY_API_KEY` | Pesquisa de Preços de Mercado | [Tavily AI](https://tavily.com/) *(Plano gratuito generoso)* |
| `SERPER_API_KEY` | Pesquisa de Preços Google | [Serper.dev](https://serper.dev/) |
| `DEEPSEEK_API_KEY` | Copywriting e Precificação | [DeepSeek Platform](https://platform.deepseek.com/) *(Centavos de real)* |
| `TELEGRAM_BOT_TOKEN` | *(Opcional)* Notificações no Telegram | Bot [@BotFather](https://t.me/botfather) |

> 💡 **Nota:** O sistema possui mecanismos de fallback heurísticos integrados. Você pode testar e utilizar todas as telas localmente mesmo sem preencher todas as chaves de API.

---

## 🌐 Deploy em VPS Linux (Google Cloud / Ubuntu)

Consulte o arquivo [`DEPLOY.md`](./DEPLOY.md) para o passo a passo completo de provisionamento com Gunicorn, Nginx, Systemd, rotina de backup diário e certificado SSL HTTPS gratuito com Certbot.
