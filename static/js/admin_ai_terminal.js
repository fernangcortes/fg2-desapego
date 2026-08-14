/**
 * Django Admin Transparent Hacker Stream - Hub de Desapego
 * Stream de logs 100% transparente, sem box, movível, com resize via wheel e fechar ao clicar fora.
 */

(function () {
    'use strict';

    const AdminAITerminal = {
        rootEl: null,
        bodyEl: null,
        pillEl: null,
        statusDot: null,
        titleLabel: null,
        isOpen: false,
        isMinimized: false,
        isDragging: false,
        dragOffsetX: 0,
        dragOffsetY: 0,
        currentFontSize: 11.5,

        init() {
            this.buildDOM();
            this.bindEvents();
            this.initDraggable();
            this.initWheelResize();
            this.initClickOutside();
            this.restoreGeometry();
        },

        buildDOM() {
            if (document.getElementById('admin-ai-terminal-root')) return;

            // 1. Transparent Movable Root
            const terminal = document.createElement('div');
            terminal.id = 'admin-ai-terminal-root';
            terminal.className = 'terminal-hidden';
            terminal.innerHTML = `
                <div class="ai-terminal-header" id="ai-term-header">
                    <div class="ai-terminal-drag-label">
                        <span class="grip-icon" title="Arraste para mover">⠿</span>
                        <span class="terminal-status-dot" id="ai-term-dot"></span>
                        <span class="terminal-name" id="ai-term-name">ai-stream</span>
                    </div>
                    <div class="ai-terminal-actions">
                        <button type="button" class="ai-terminal-action-btn" id="ai-term-clear" title="Limpar logs">clear</button>
                        <button type="button" class="ai-terminal-action-btn" id="ai-term-min" title="Minimizar">−</button>
                        <button type="button" class="ai-terminal-action-btn btn-close" id="ai-term-close" title="Fechar">×</button>
                    </div>
                </div>
                <div class="ai-terminal-body" id="ai-term-body">
                    <!-- Logs stream here -->
                </div>
            `;
            document.body.appendChild(terminal);

            // 2. Minimized Transparent Chip
            const pill = document.createElement('div');
            pill.id = 'admin-ai-terminal-pill';
            pill.className = 'pill-hidden';
            pill.innerHTML = `
                <span class="pill-dot" id="ai-pill-dot"></span>
                <span id="ai-pill-text">❯ ai: pronto</span>
            `;
            document.body.appendChild(pill);

            this.rootEl = terminal;
            this.bodyEl = document.getElementById('ai-term-body');
            this.pillEl = pill;
            this.statusDot = document.getElementById('ai-term-dot');
            this.titleLabel = document.getElementById('ai-term-name');

            this.log('❯ ai-engine v2.5 initialized', 'info');
        },

        bindEvents() {
            document.getElementById('ai-term-close')?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.close();
            });
            document.getElementById('ai-term-min')?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.minimize();
            });
            document.getElementById('ai-term-clear')?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.clear();
            });
            this.pillEl?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.restore();
            });

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
                            this.log('✕ nenhum item selecionado', 'err');
                            return;
                        }

                        this.runBatch(ids);
                    }
                });
            }

            // Keyboard Escape to close
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen) {
                    this.close();
                }
            });
        },

        /* Click outside terminal closes it */
        initClickOutside() {
            document.addEventListener('pointerdown', (e) => {
                if (!this.isOpen || this.isMinimized) return;

                const isInsideTerminal = this.rootEl.contains(e.target);
                const isClickOnAiBtn = e.target.closest('.admin-ai-action-btn, #admin-ai-terminal-pill');

                if (!isInsideTerminal && !isClickOnAiBtn) {
                    this.close();
                }
            });
        },

        /* Wheel resize on hover */
        initWheelResize() {
            const header = document.getElementById('ai-term-header');

            const handleWheelResize = (e) => {
                // Resize if scrolling over header OR if Ctrl/Alt is held anywhere on terminal
                const isOverHeader = e.target.closest('.ai-terminal-header');
                const hasModifier = e.ctrlKey || e.altKey || e.shiftKey;

                if (isOverHeader || hasModifier) {
                    e.preventDefault();
                    e.stopPropagation();

                    const delta = e.deltaY < 0 ? 1 : -1;
                    const rect = this.rootEl.getBoundingClientRect();

                    let newWidth = rect.width + (delta * 24);
                    let newHeight = rect.height + (delta * 16);
                    let newFont = this.currentFontSize + (delta * 0.4);

                    // Clamp values
                    newWidth = Math.max(220, Math.min(newWidth, window.innerWidth - 40));
                    newHeight = Math.max(90, Math.min(newHeight, window.innerHeight - 50));
                    newFont = Math.max(9, Math.min(newFont, 16));

                    this.rootEl.style.width = `${newWidth}px`;
                    this.rootEl.style.height = `${newHeight}px`;
                    this.rootEl.style.fontSize = `${newFont}px`;
                    this.currentFontSize = newFont;

                    this.saveGeometry();
                }
            };

            this.rootEl.addEventListener('wheel', handleWheelResize, { passive: false });

            // Listen to manual mouse resize to persist dimensions
            const resizeObserver = new ResizeObserver(() => {
                if (this.isOpen && !this.isMinimized && !this.isDragging) {
                    this.saveGeometry();
                }
            });
            resizeObserver.observe(this.rootEl);
        },

        /* Draggable System */
        initDraggable() {
            const header = document.getElementById('ai-term-header');
            if (!header) return;

            const onMouseDown = (e) => {
                if (e.target.closest('.ai-terminal-actions')) return;

                this.isDragging = true;
                this.rootEl.classList.add('is-dragging');

                const rect = this.rootEl.getBoundingClientRect();
                this.dragOffsetX = e.clientX - rect.left;
                this.dragOffsetY = e.clientY - rect.top;

                document.addEventListener('mousemove', onMouseMove);
                document.addEventListener('mouseup', onMouseUp);
                e.preventDefault();
            };

            const onMouseMove = (e) => {
                if (!this.isDragging) return;

                let left = e.clientX - this.dragOffsetX;
                let top = e.clientY - this.dragOffsetY;

                // Viewport boundaries
                const maxLeft = window.innerWidth - this.rootEl.offsetWidth - 10;
                const maxTop = window.innerHeight - this.rootEl.offsetHeight - 10;

                left = Math.max(10, Math.min(left, maxLeft));
                top = Math.max(10, Math.min(top, maxTop));

                this.rootEl.style.left = `${left}px`;
                this.rootEl.style.top = `${top}px`;
                this.rootEl.style.right = 'auto';
                this.rootEl.style.bottom = 'auto';
            };

            const onMouseUp = () => {
                if (!this.isDragging) return;
                this.isDragging = false;
                this.rootEl.classList.remove('is-dragging');

                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);

                this.saveGeometry();
            };

            header.addEventListener('mousedown', onMouseDown);
        },

        saveGeometry() {
            const rect = this.rootEl.getBoundingClientRect();
            const geometry = {
                left: rect.left,
                top: rect.top,
                width: rect.width,
                height: rect.height,
                fontSize: this.currentFontSize
            };
            try {
                localStorage.setItem('hub_ai_term_geometry', JSON.stringify(geometry));
            } catch (_) {}
        },

        restoreGeometry() {
            try {
                const saved = localStorage.getItem('hub_ai_term_geometry');
                if (saved) {
                    const geo = JSON.parse(saved);
                    if (geo.left > 0 && geo.left < window.innerWidth - 60 && geo.top > 0 && geo.top < window.innerHeight - 40) {
                        this.rootEl.style.left = `${geo.left}px`;
                        this.rootEl.style.top = `${geo.top}px`;
                        this.rootEl.style.right = 'auto';
                        this.rootEl.style.bottom = 'auto';
                    }
                    if (geo.width >= 200 && geo.width <= window.innerWidth) {
                        this.rootEl.style.width = `${geo.width}px`;
                    }
                    if (geo.height >= 80 && geo.height <= window.innerHeight) {
                        this.rootEl.style.height = `${geo.height}px`;
                    }
                    if (geo.fontSize && geo.fontSize >= 9 && geo.fontSize <= 18) {
                        this.currentFontSize = geo.fontSize;
                        this.rootEl.style.fontSize = `${geo.fontSize}px`;
                    }
                }
            } catch (_) {}
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

        clear() {
            this.bodyEl.innerHTML = '';
            this.log('❯ stream cleared', 'info');
        },

        setStatus(status) {
            const pillDot = document.getElementById('ai-pill-dot');
            const pillText = document.getElementById('ai-pill-text');

            this.statusDot.className = 'terminal-status-dot';
            if (pillDot) pillDot.className = 'pill-dot';

            if (status === 'running') {
                this.statusDot.classList.add('is-running');
                if (pillDot) pillDot.classList.add('is-running');
                this.titleLabel.textContent = 'ai-running...';
                if (pillText) pillText.textContent = '❯ ai: processando...';
            } else if (status === 'error') {
                this.statusDot.classList.add('is-error');
                this.titleLabel.textContent = 'ai-error';
                if (pillText) pillText.textContent = '❯ ai: erro';
            } else {
                this.titleLabel.textContent = 'ai-stream';
                if (pillText) pillText.textContent = '❯ ai: pronto';
            }
        },

        getTime() {
            const now = new Date();
            const pad = (n) => String(n).padStart(2, '0');
            return `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
        },

        log(text, type = 'normal', isSub = false) {
            const row = document.createElement('div');
            row.className = 'term-row';

            let sym = '❯';
            let symClass = '';
            if (type === 'proc') { sym = '⌁'; symClass = 'sym-proc'; }
            else if (type === 'ok') { sym = '✓'; symClass = 'term-success'; }
            else if (type === 'err') { sym = '✕'; symClass = 'sym-err'; }
            else if (type === 'info') { sym = '·'; symClass = 'sym-info'; }

            if (isSub) {
                row.innerHTML = `
                    <span class="term-time">${this.getTime()}</span>
                    <span class="term-sub ${type === 'ok' ? 'term-success' : (type === 'err' ? 'term-error' : '')}">
                        <span class="${symClass}">${sym}</span> ${text}
                    </span>
                `;
            } else {
                row.innerHTML = `
                    <span class="term-time">${this.getTime()}</span>
                    <span class="term-sym ${symClass}">${sym}</span>
                    <span class="term-text ${type === 'ok' ? 'term-success' : (type === 'err' ? 'term-error' : '')}">${text}</span>
                `;
            }

            this.bodyEl.appendChild(row);
            this.scrollToBottom();
            return row;
        },

        scrollToBottom() {
            if (this.bodyEl) {
                this.bodyEl.scrollTop = this.bodyEl.scrollHeight;
            }
        },

        async runItem(itemId, itemTitle, btnElement = null) {
            this.open();
            this.setStatus('running');
            if (btnElement) btnElement.classList.add('is-running');

            this.log(`target #${itemId}: <span class="term-highlight">"${itemTitle}"</span>`);

            let stepIndex = 0;
            const steps = [
                'vision: analyzing photos via Gemini Multimodal...',
                'market: searching live quotes & specs in Brazil...',
                'copy: generating tech specs and honest copy...',
                'sync: updating database records & links...'
            ];

            const stepTimer = setInterval(() => {
                if (stepIndex < steps.length) {
                    this.log(steps[stepIndex], 'proc', true);
                    stepIndex++;
                }
            }, 1900);

            try {
                const response = await fetch(`/ai/process/${itemId}/?format=json`, {
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                clearInterval(stepTimer);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const data = await response.json();

                if (data.success) {
                    this.setStatus('idle');
                    const precoUsado = data.preco_usado_formatado || (data.preco_usado ? `R$ ${data.preco_usado}` : '-');
                    const precoNovo = data.preco_novo_formatado || (data.preco_novo_referencia ? `R$ ${data.preco_novo_referencia}` : '-');
                    const links = data.num_urls || (data.urls_referencia ? data.urls_referencia.length : 0);

                    this.log(`synced: <span class="term-highlight">"${data.titulo || itemTitle}"</span>`, 'ok', true);
                    if (data.slug) {
                        this.log(`slug: <span class="term-accent">/item/${data.slug}/</span>`, 'info', true);
                    }
                    this.log(`venda: <span class="term-accent">${precoUsado}</span> | novo: ${precoNovo} | links: ${links}`, 'ok', true);

                    this.updateTableRow(itemId, data);
                    this.updateFormFields(data);
                } else {
                    this.setStatus('error');
                    this.log(`error: ${data.error || 'Falha no processamento'}`, 'err', true);
                }

            } catch (err) {
                clearInterval(stepTimer);
                this.setStatus('error');
                this.log(`network error: ${err.message}`, 'err', true);
            } finally {
                if (btnElement) btnElement.classList.remove('is-running');
            }
        },

        async runBatch(itemIds) {
            this.open();
            this.setStatus('running');
            this.log(`batch: starting ${itemIds.length} item(s)...`);

            let successCount = 0;
            let failCount = 0;

            for (let i = 0; i < itemIds.length; i++) {
                const id = itemIds[i];
                const row = document.querySelector(`input[name="_selected_action"][value="${id}"]`)?.closest('tr');
                const titleLink = row ? row.querySelector('.field-titulo a, th.field-titulo a') : null;
                const itemTitle = titleLink ? titleLink.textContent.trim() : `Item #${id}`;
                const btn = row ? row.querySelector('.admin-ai-action-btn') : null;

                this.log(`[${i + 1}/${itemIds.length}] item #${id}: "${itemTitle}"`, 'proc');

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
                        this.log(`✓ synced: ${data.preco_usado_formatado || data.preco_usado}`, 'ok', true);
                        this.updateTableRow(id, data);
                    } else {
                        failCount++;
                        this.log(`✕ error: ${data.error || 'failed'}`, 'err', true);
                    }
                } catch (err) {
                    failCount++;
                    this.log(`✕ network error: ${err.message}`, 'err', true);
                } finally {
                    if (btn) btn.classList.remove('is-running');
                }
            }

            if (failCount === 0) {
                this.setStatus('idle');
                this.log(`batch completed: ${successCount}/${itemIds.length} OK`, 'ok');
            } else {
                this.setStatus('error');
                this.log(`batch done: ${successCount} OK, ${failCount} fail`, 'err');
            }
        },

        updateTableRow(itemId, data) {
            const checkbox = document.querySelector(`input[name="_selected_action"][value="${itemId}"]`);
            const aiBtn = document.querySelector(`.admin-ai-action-btn[data-item-id="${itemId}"]`);
            const tr = checkbox ? checkbox.closest('tr') : (aiBtn ? aiBtn.closest('tr') : null);

            if (!tr) return;

            const titleLink = tr.querySelector('.field-titulo a, th.field-titulo a');
            if (titleLink && data.titulo) {
                titleLink.textContent = data.titulo;
            }

            const precoUsadoCell = tr.querySelector('.field-preco_usado_formatado');
            if (precoUsadoCell && (data.preco_usado_formatado || data.preco_usado)) {
                precoUsadoCell.textContent = data.preco_usado_formatado || `R$ ${parseFloat(data.preco_usado).toFixed(2).replace('.', ',')}`;
            }

            const precoNovoCell = tr.querySelector('.field-preco_novo_formatado');
            if (precoNovoCell && (data.preco_novo_formatado || data.preco_novo_referencia)) {
                precoNovoCell.textContent = data.preco_novo_formatado || `R$ ${parseFloat(data.preco_novo_referencia).toFixed(2).replace('.', ',')}`;
            }

            const categoriaCell = tr.querySelector('.field-categoria');
            if (categoriaCell && (data.categoria_display || data.categoria)) {
                categoriaCell.textContent = data.categoria_display || data.categoria;
            }

            tr.classList.remove('row-ai-updated');
            void tr.offsetWidth;
            tr.classList.add('row-ai-updated');
        },

        updateFormFields(data) {
            const setVal = (id, val) => {
                const el = document.getElementById(id);
                if (el && val) el.value = val;
            };

            setVal('id_titulo', data.titulo);
            setVal('id_slug', data.slug);
            setVal('id_preco_usado', data.preco_usado);
            setVal('id_preco_novo_referencia', data.preco_novo_referencia);
            setVal('id_preco_aluguel', data.preco_aluguel);
            setVal('id_categoria', data.categoria);
            setVal('id_descricao_ia', data.descricao_ia);
            setVal('id_defeitos_visiveis', data.defeitos_visiveis);
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => AdminAITerminal.init());
    } else {
        AdminAITerminal.init();
    }

    window.AdminAITerminal = AdminAITerminal;
})();
