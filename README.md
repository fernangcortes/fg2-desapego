# 🏷️ Hub de Desapego Inteligente

Sistema pessoal e moderno para gerenciamento, precificação por Inteligência Artificial e venda/aluguel de centenas de itens usados por um casal.

Construído com **Python 3.12**, **Django 5.1**, **SQLite**, **TailwindCSS**, **HTMX**, **PWA (Progressive Web App)** e arquitetura de IA (*Chain of Thought*).

---

## ✨ Principais Funcionalidades

1. **📱 PWA Mobile com Câmera Nativa (`/upload/`)**:
   - Interface mobile-first otimizada para tirar fotos sequenciais de produtos com a câmera traseira do smartphone.
   - Prévia instantânea de fotos, remoção de imagens e seleção visual da foto de capa.
   - Salvamento automático de rascunhos com suporte a anotações rápidas.

2. **🧠 Pipeline Inteligente de IA (`ai_engine`)**:
   - **Visão Computacional (Google Gemini 1.5/2.0 Flash ou Groq Llama 3.2 Vision):** Identifica produto, marca, modelo e realiza detecção rigorosa de **marcas de uso e defeitos visíveis**.
   - **Pesquisa de Mercado (Tavily API ou Serper API):** Coleta preços de referência de itens novos (Amazon/Mercado Livre) e usados (OLX/Enjoei) com links de origem.
   - **Copywriting Transparente (DeepSeek API):** Redação persuasiva focada em **100% de honestidade**, apontando avarias, sugerindo preços justos de venda e de aluguel.
   - **Notificações:** Alerta no Telegram quando novos itens estão prontos para aprovação.

3. **🛍️ Vitrine Pública Responsiva (`/`)**:
   - Exibição de itens aprovados com abas para *Todos*, *Venda* e *Aluguel*.
   - Filtros dinâmicos por categoria e busca em tempo real por produto/marca.
   - Comparativo de economia real em relação ao produto novo nas lojas.

4. **🔍 Página de Detalhes com Transparência Total (`/item/<slug>/`)**:
   - Galeria interativa de fotos em alta resolução.
   - Box destacado exibindo com clareza qualquer marca de uso ou defeito.
   - **Botão Inteligente de Contato ("Tenho Interesse"):** Abre o WhatsApp do vendedor com mensagem de cotação oficial pré-preenchida:
     ```text
     "Olá, vi seu anúncio no site e tenho interesse no [Produto] pelo valor de [Preço]. Segue link: [Link]"
     ```
   - Botões diretos para Telegram, E-mail e cópia de chave PIX em 1 clique.

5. **📋 Exportador para Marketplaces (`marketplace`)**:
   - Botões e modal no Admin para copiar a descrição formatada em 1 clique para:
     - **OLX:** Texto puro, sem markdown quebrado, tópicos claros com emojis.
     - **Mercado Livre:** Formatação estruturada profissional.
     - **Facebook Marketplace:** Texto direto e atraente para grupos.

---

## 🛠️ Stack Tecnológica

| Componente | Tecnologia |
| :--- | :--- |
| **Linguagem & Backend** | Python 3.12+ com Django 5.1.x |
| **Banco de Dados** | SQLite (desenvolvimento e VPS) |
| **Frontend** | Django Templates + TailwindCSS (CDN) + HTMX |
| **Mobile** | PWA (Progressive Web App com `manifest.json` e `service-worker.js`) |
| **Visão Computacional** | Google Gemini Flash / Groq Llama 3.2 Vision |
| **Pesquisa de Preços** | Tavily Search API / Serper API |
| **Copywriting** | DeepSeek API (deepseek-chat) |
| **Deploy VPS** | Ubuntu Linux + Gunicorn + Nginx + Systemd + Certbot SSL |

---

## 🚀 Como Executar Localmente

### 1. Clonar o repositório e criar o ambiente virtual
```bash
# Clone o repositório
git clone https://github.com/SEU_USUARIO/fgc2-desapego.git
cd fgc2-desapego

# Crie e ative o ambiente virtual
python -m venv venv

# No Windows:
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

- **Vitrine Pública:** [http://localhost:8000/](http://localhost:8000/)
- **Upload Rápido Mobile:** [http://localhost:8000/upload/](http://localhost:8000/upload/)
- **Painel Admin:** [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

## 🧪 Execução de Testes Automatizados

O projeto possui cobertura completa de testes unitários e de integração (23 testes):

```bash
python manage.py test
```

---

## 🔑 Guia de Chaves de API

Para ativar a inteligência artificial, adicione as chaves no arquivo `.env`:

| Serviço | Função | Onde Obter |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Visão Computacional / Fotos | [Google AI Studio](https://aistudio.google.com/) |
| `GROQ_API_KEY` | Visão Alternativa (Llama 3.2) | [Groq Console](https://console.groq.com/) |
| `TAVILY_API_KEY` | Pesquisa de Preços de Mercado | [Tavily AI](https://tavily.com/) |
| `SERPER_API_KEY` | Pesquisa de Preços Google | [Serper.dev](https://serper.dev/) |
| `DEEPSEEK_API_KEY` | Copywriting e Precificação | [DeepSeek Platform](https://platform.deepseek.com/) |
| `TELEGRAM_BOT_TOKEN` | Notificações no Telegram | Bot [@BotFather](https://t.me/botfather) |

> **Nota:** O sistema possui mecanismos de fallback heurísticos integrados. Você pode testar e utilizar todas as telas localmente mesmo sem preencher todas as chaves de API.

---

## 🌐 Deploy em VPS Linux

Consulte o arquivo [`DEPLOY.md`](./DEPLOY.md) para o passo a passo completo com Gunicorn, Nginx, Systemd e Certbot SSL.
