/**
 * Django Admin AI Pipeline Terminal - Hub de Desapego
 * Terminal interativo e em tempo real para orquestração de IA direto na página.
 * Não-bloqueante, sem modal, com suporte a processamento individual e em lote.
 */

(function () {
    'use strict';

    const AdminAITerminal = {
        rootEl: null,
        bodyEl: null,
        pillEl: null,
        badgeEl: null,
        titleEl: null,
        isOpen: false,
        isMinimized: false,
        isProcessing: false,

        init() {
            this.buildDOM();
            this.bindEvents();
        },

        buildDOM() {
            if (document.getElementById('admin-ai-terminal-root')) return;

            // 1. Terminal Window Container
            const terminal = document.createElement('div');
            terminal.id = 'admin-ai-terminal-root';
            terminal.className = 'terminal-hidden';
            terminal.innerHTML = `
                <div class="ai-terminal-header">
                    <div class="ai-terminal-window-dots">
                        <span class="ai-terminal-dot dot-close" id="ai-term-btn-close" title="Fechar Terminal"></span>
                        <span class="ai-terminal-dot dot-minimize" id="ai-term-btn-minimize" title="Minimizar Terminal"></span>
                        <span class="ai-terminal-dot dot-maximize" id="ai-term-btn-maximize" title="Alternar Tamanho"></span>
                    </div>

                    <div class="ai-terminal-title">
                        <span>⚡</span>
                        <span>hub-desapego@ai:</span>
                        <span class="terminal-host">~/orchestrator</span>
                    </div>

                    <div class="ai-terminal-header-actions">
                        <div class="ai-terminal-badge status-idle" id="ai-term-status">
                            <span class="badge-dot"></span>
                            <span class="badge-text">PRONTO</span>
                        </div>
                        <button type="button" class="ai-terminal-btn-tool" id="ai-term-btn-clear" title="Limpar Logs">🧹 Limpar</button>
                    </div>
                </div>

                <div class="ai-terminal-body" id="ai-term-body">
                    <!-- Logs dynamically appended here -->
                </div>
            `;
            document.body.appendChild(terminal);

            // 2. Floating Minimized Pill
            const pill = document.createElement('div');
            pill.id = 'admin-ai-terminal-pill';
            pill.className = 'pill-hidden';
            pill.innerHTML = `
                <span class="pill-pulse"></span>
                <span id="ai-pill-text">⚡ Terminal IA</span>
            `;
            document.body.appendChild(pill);

            this.rootEl = terminal;
            this.bodyEl = document.getElementById('ai-term-body');
            this.pillEl = pill;
            this.badgeEl = document.getElementById('ai-term-status');
            this.titleEl = document.querySelector('.ai-terminal-title');

            // Add initial welcome command
            this.logCommand('ai-pipeline --version');
            this.log('Hub de Desapego AI Engine v2.5 [Gemini Flash + Tavily + DeepSeek]', { tag: 'INIT' });
        },

        bindEvents() {
            // Window controls
            document.getElementById('ai-term-btn-close')?.addEventListener('click', () => this.close());
            document.getElementById('ai-term-btn-minimize')?.addEventListener('click', () => this.minimize());
            document.getElementById('ai-term-btn-maximize')?.addEventListener('click', () => this.toggleMaximize());
            document.getElementById('ai-term-btn-clear')?.addEventListener('click', () => this.clear());
            this.pillEl?.addEventListener('click', () => this.restore());

            // Global click for row AI action buttons
            document.addEventListener('click', (e) => {
                const aiBtn = e.target.closest('.admin-ai-action-btn, a[href*="/ai/process/"]');
                if (!aiBtn) return;

                e.preventDefault();
                e.stopPropagation();

                const itemId = aiBtn.getAttribute('data-item-id') || this.extractIdFromHref(aiBtn.getAttribute('href'));
                const itemTitle = aiBtn.getAttribute('data-item-title') || `Item #${itemId}`;

                if (itemId) {
                    this.runItem(itemId, itemTitle, aiBtn);
                }
            });

            // Intercept Batch Action form submit in Changelist
            const changelistForm = document.getElementById('changelist-form');
            if (changelistForm) {
                changelistForm.addEventListener('submit', (e) => {
                    const actionSelect = changelistForm.querySelector('select[name="action"]');
                    if (actionSelect && actionSelect.value === 'processar_com_ia') {
                        e.preventDefault();
                        e.stopPropagation();

                        const selectedCheckboxes = changelistForm.querySelectorAll('input[name="_selected_action"]:checked');
                        const ids = Array.from(selectedCheckboxes).map(cb => cb.value);

                        if (ids.length === 0) {
                            this.open();
                            this.log('Nenhum item selecionado para a ação em lote.', { tag: 'ERROR' });
                            return;
                        }

                        this.runBatch(ids);
                    }
                });
            }

            // Keyboard shortcut (Escape to close/minimize)
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen && !this.isMinimized) {
                    this.minimize();
                }
            });
        },

        extractIdFromHref(href) {
            if (!href) return null;
            const match = href.match(/\/ai\/process\/(\d+)\//) || href.match(/\/item\/(\d+)\//);
            return match ? match[1] : null;
        },

        open() {
            this.rootEl.classList.remove('terminal-hidden', 'terminal-minimized');
            this.pillEl.classList.add('pill-hidden');
            this.isOpen = true;
            this.isMinimized = false;
            this.scrollToBottom();
        },

        close() {
            this.rootEl.classList.add('terminal-hidden');
            this.pillEl.classList.add('pill-hidden');
            this.isOpen = false;
            this.isMinimized = false;
        },

        minimize() {
            this.rootEl.classList.add('terminal-minimized');
            this.pillEl.classList.remove('pill-hidden');
            this.isMinimized = true;
        },

        restore() {
            this.open();
        },

        toggleMaximize() {
            this.rootEl.classList.toggle('terminal-maximized');
            this.scrollToBottom();
        },

        clear() {
            this.bodyEl.innerHTML = '';
            this.logCommand('clear');
            this.log('Logs limpos. Terminal pronto.', { tag: 'INIT' });
        },

        setStatus(status, label) {
            this.badgeEl.className = `ai-terminal-badge status-${status}`;
            const textSpan = this.badgeEl.querySelector('.badge-text');
            if (textSpan) textSpan.textContent = label || status.toUpperCase();

            // Update pill text
            const pillText = document.getElementById('ai-pill-text');
            if (pillText) {
                pillText.textContent = `⚡ Terminal IA (${label || status})`;
            }
        },

        getCurrentTime() {
            const now = new Date();
            const pad = (n) => String(n).padStart(2, '0');
            return `[${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}]`;
        },

        logCommand(cmd) {
            const line = document.createElement('div');
            line.className = 'terminal-line';
            line.innerHTML = `
                <span class="terminal-time">${this.getCurrentTime()}</span>
                <span class="terminal-text">
                    <span class="terminal-prompt">root@desapego-ai:~$</span>
                    <span class="terminal-command">${cmd}</span>
                </span>
            `;
            this.bodyEl.appendChild(line);
            this.scrollToBottom();
        },

        log(text, options = {}) {
            const tag = options.tag || '';
            const isDetail = options.isDetail || false;

            const line = document.createElement('div');
            line.className = 'terminal-line';

            let tagHtml = '';
            if (tag) {
                const tagClass = `tag-${tag.toLowerCase()}`;
                tagHtml = `<span class="terminal-tag ${tagClass}">[${tag}]</span>`;
            }

            if (isDetail) {
                line.innerHTML = `
                    <span class="terminal-time">${this.getCurrentTime()}</span>
                    <span class="terminal-text">
                        <div class="terminal-detail">${tagHtml}${text}</div>
                    </span>
                `;
            } else {
                line.innerHTML = `
                    <span class="terminal-time">${this.getCurrentTime()}</span>
                    <span class="terminal-text">${tagHtml}${text}</span>
                `;
            }

            this.bodyEl.appendChild(line);
            this.scrollToBottom();
            return line;
        },

        logSummaryCard(data) {
            const card = document.createElement('div');
            card.className = 'terminal-summary-card';
            card.innerHTML = `
                <div class="summary-title">🎯 ${data.titulo || 'Item Processado'}</div>
                <div class="summary-grid">
                    <div class="summary-item">Preço Venda: <strong>${data.preco_usado_formatado || 'R$ ' + (data.preco_usado || '0,00')}</strong></div>
                    <div class="summary-item">Preço Novo Ref: <strong>${data.preco_novo_formatado || 'R$ ' + (data.preco_novo_referencia || '0,00')}</strong></div>
                    <div class="summary-item">Categoria: <strong>${data.categoria_display || data.categoria || '-'}</strong></div>
                    <div class="summary-item">Referências: <strong>${data.num_urls || (data.urls_referencia ? data.urls_referencia.length : 0)} links</strong></div>
                </div>
            `;
            this.bodyEl.appendChild(card);
            this.scrollToBottom();
        },

        scrollToBottom() {
            if (this.bodyEl) {
                this.bodyEl.scrollTop = this.bodyEl.scrollHeight;
            }
        },

        async runItem(itemId, itemTitle, btnElement = null) {
            this.open();
            this.setStatus('running', 'EXECUTANDO');
            if (btnElement) btnElement.classList.add('is-running');

            this.logCommand(`ai-orchestrator.py --item=${itemId} --mode=full`);
            this.log(`Iniciando Chain of Thought para #${itemId} ("${itemTitle}")...`, { tag: 'INIT' });

            // Simulated stepwise streaming logs while the network request is in flight
            let stepIndex = 0;
            const steps = [
                { tag: 'VISION', text: '👁️ Analisando fotos via Gemini Flash Multimodal (marca, modelo e avarias)...' },
                { tag: 'MARKET', text: '🔍 Consultando referências de mercado e cotações (ML, Amazon e Google)...' },
                { tag: 'COPY', text: '✍️ Gerando copywriting técnico, transparência total e precificação...' },
                { tag: 'DB', text: '💾 Atualizando registro no banco de dados e gerando links de referência...' }
            ];

            const stepTimer = setInterval(() => {
                if (stepIndex < steps.length) {
                    const step = steps[stepIndex];
                    this.log(step.text, { tag: step.tag, isDetail: true });
                    stepIndex++;
                }
            }, 1800);

            try {
                const response = await fetch(`/ai/process/${itemId}/?format=json`, {
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                clearInterval(stepTimer);

                if (!response.ok) {
                    throw new Error(`Servidor retornou status HTTP ${response.status}`);
                }

                const data = await response.json();

                if (data.success) {
                    this.setStatus('done', 'CONCLUÍDO');
                    this.log(`✨ Processamento concluído com sucesso para o Item #${itemId}!`, { tag: 'SUCCESS' });
                    this.logSummaryCard(data);

                    // Update Table Row dynamically if present
                    this.updateTableRow(itemId, data);

                    // Update Form Fields if user is currently editing this item
                    this.updateFormFields(data);

                } else {
                    this.setStatus('error', 'ERRO');
                    this.log(`Falha no processamento: ${data.error || 'Erro desconhecido'}`, { tag: 'ERROR' });
                }

            } catch (err) {
                clearInterval(stepTimer);
                this.setStatus('error', 'ERRO');
                this.log(`Exceção durante a requisição: ${err.message}`, { tag: 'ERROR' });
            } finally {
                if (btnElement) btnElement.classList.remove('is-running');
            }
        },

        async runBatch(itemIds) {
            this.open();
            this.setStatus('running', 'LOTE');
            this.logCommand(`ai-orchestrator.py --batch --count=${itemIds.length}`);
            this.log(`Iniciando processamento em lote de ${itemIds.length} item(ns) selecionado(s)...`, { tag: 'BATCH' });

            let successCount = 0;
            let failCount = 0;

            for (let i = 0; i < itemIds.length; i++) {
                const id = itemIds[i];
                const row = document.querySelector(`input[name="_selected_action"][value="${id}"]`)?.closest('tr');
                const titleLink = row ? row.querySelector('.field-titulo a, th.field-titulo a') : null;
                const itemTitle = titleLink ? titleLink.textContent.trim() : `Item #${id}`;
                const btn = row ? row.querySelector('.admin-ai-action-btn') : null;

                this.log(`[${i + 1}/${itemIds.length}] Processando Item #${id} ("${itemTitle}")...`, { tag: 'BATCH' });

                if (btn) btn.classList.add('is-running');

                try {
                    const response = await fetch(`/ai/process/${id}/?format=json`, {
                        headers: {
                            'Accept': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });

                    const data = await response.json();

                    if (data.success) {
                        successCount++;
                        this.log(`✓ #${id} OK: "${data.titulo}" | Preço: ${data.preco_usado_formatado || data.preco_usado}`, { tag: 'SUCCESS', isDetail: true });
                        this.updateTableRow(id, data);
                    } else {
                        failCount++;
                        this.log(`✕ #${id} Erro: ${data.error || 'Falha'}`, { tag: 'ERROR', isDetail: true });
                    }
                } catch (err) {
                    failCount++;
                    this.log(`✕ #${id} Exceção de rede: ${err.message}`, { tag: 'ERROR', isDetail: true });
                } finally {
                    if (btn) btn.classList.remove('is-running');
                }
            }

            if (failCount === 0) {
                this.setStatus('done', 'CONCLUÍDO');
                this.log(`🎉 Processamento em lote concluído com sucesso! ${successCount} de ${itemIds.length} itens processados.`, { tag: 'SUCCESS' });
            } else {
                this.setStatus('error', 'AVISO');
                this.log(`Lote finalizado com ${successCount} sucesso(s) e ${failCount} falha(s).`, { tag: 'BATCH' });
            }
        },

        updateTableRow(itemId, data) {
            // Locate table row by selected checkbox value or action link
            const checkbox = document.querySelector(`input[name="_selected_action"][value="${itemId}"]`);
            const aiBtn = document.querySelector(`.admin-ai-action-btn[data-item-id="${itemId}"]`);
            const tr = checkbox ? checkbox.closest('tr') : (aiBtn ? aiBtn.closest('tr') : null);

            if (!tr) return;

            // 1. Update Title Link
            const titleLink = tr.querySelector('.field-titulo a, th.field-titulo a');
            if (titleLink && data.titulo) {
                titleLink.textContent = data.titulo;
            }

            // 2. Update Used Price
            const precoUsadoCell = tr.querySelector('.field-preco_usado_formatado');
            if (precoUsadoCell && (data.preco_usado_formatado || data.preco_usado)) {
                precoUsadoCell.textContent = data.preco_usado_formatado || `R$ ${parseFloat(data.preco_usado).toFixed(2).replace('.', ',')}`;
            }

            // 3. Update New Ref Price
            const precoNovoCell = tr.querySelector('.field-preco_novo_formatado');
            if (precoNovoCell && (data.preco_novo_formatado || data.preco_novo_referencia)) {
                precoNovoCell.textContent = data.preco_novo_formatado || `R$ ${parseFloat(data.preco_novo_referencia).toFixed(2).replace('.', ',')}`;
            }

            // 4. Update Category
            const categoriaCell = tr.querySelector('.field-categoria');
            if (categoriaCell && (data.categoria_display || data.categoria)) {
                categoriaCell.textContent = data.categoria_display || data.categoria;
            }

            // 5. Trigger live update highlight glow on the row
            tr.classList.remove('row-ai-updated');
            void tr.offsetWidth; // Force reflow
            tr.classList.add('row-ai-updated');
        },

        updateFormFields(data) {
            // If the user is on the change form page (/admin/core/item/<id>/change/)
            const tituloInput = document.getElementById('id_titulo');
            if (tituloInput && data.titulo) {
                tituloInput.value = data.titulo;
            }

            const precoUsadoInput = document.getElementById('id_preco_usado');
            if (precoUsadoInput && data.preco_usado) {
                precoUsadoInput.value = data.preco_usado;
            }

            const precoNovoInput = document.getElementById('id_preco_novo_referencia');
            if (precoNovoInput && data.preco_novo_referencia) {
                precoNovoInput.value = data.preco_novo_referencia;
            }

            const precoAluguelInput = document.getElementById('id_preco_aluguel');
            if (precoAluguelInput && data.preco_aluguel) {
                precoAluguelInput.value = data.preco_aluguel;
            }

            const categoriaSelect = document.getElementById('id_categoria');
            if (categoriaSelect && data.categoria) {
                categoriaSelect.value = data.categoria;
            }

            const descricaoIaTextarea = document.getElementById('id_descricao_ia');
            if (descricaoIaTextarea && data.descricao_ia) {
                descricaoIaTextarea.value = data.descricao_ia;
            }

            const defeitosTextarea = document.getElementById('id_defeitos_visiveis');
            if (defeitosTextarea && data.defeitos_visiveis) {
                defeitosTextarea.value = data.defeitos_visiveis;
            }
        }
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => AdminAITerminal.init());
    } else {
        AdminAITerminal.init();
    }

    // Expose globally for console or custom hooks
    window.AdminAITerminal = AdminAITerminal;
})();
