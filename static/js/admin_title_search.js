/**
 * Live Title Internet Search & Smart Form Auto-Populate - Hub de Desapego
 * Dispara pesquisa na internet em tempo real ao digitar nomes no campo de título.
 * Padrão de ícones de linha (stroke-width: 1.8) e botões sutis idênticos a admin_subtle_actions.css.
 */

(function () {
    'use strict';

    let currentAbortController = null;
    let debounceTimer = null;
    let activePopover = null;
    let lastSearchedQuery = '';

    document.addEventListener('DOMContentLoaded', () => {
        initTitleSearch();
    });

    function initTitleSearch() {
        // Suporta tanto o Django Admin (#id_titulo) quanto o formulário público (#titulo_provisorio)
        const titleInputs = document.querySelectorAll('#id_titulo, #titulo_provisorio, input[name="titulo"]');
        titleInputs.forEach(input => setupTitleSearchForInput(input));
    }

    function setupTitleSearchForInput(input) {
        if (!input || input.dataset.titleSearchBound === 'true') return;
        input.dataset.titleSearchBound = 'true';

        // Cria wrapper relativo em torno do input se necessário
        let wrapper = input.parentElement;
        if (!wrapper.classList.contains('title-search-field-wrapper')) {
            const newWrapper = document.createElement('div');
            newWrapper.className = 'title-search-field-wrapper';
            input.parentNode.insertBefore(newWrapper, input);
            newWrapper.appendChild(input);
            wrapper = newWrapper;
        }

        // Cria o indicador sutil de loading dentro do campo
        const indicator = document.createElement('div');
        indicator.className = 'title-search-indicator';
        indicator.innerHTML = `
            <svg viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M12 2a10 10 0 0 1 10 10"></path>
            </svg>
            <span>Pesquisando na internet...</span>
        `;
        wrapper.appendChild(indicator);

        // Cria o container do popover flutuante
        const popover = document.createElement('div');
        popover.className = 'title-search-popover';
        wrapper.appendChild(popover);

        // Escuta digitação no input com debounce de 480ms
        input.addEventListener('input', (e) => {
            const query = e.target.value.trim();

            if (debounceTimer) clearTimeout(debounceTimer);

            if (query.length < 3) {
                indicator.classList.remove('is-visible');
                closePopover(popover);
                lastSearchedQuery = '';
                return;
            }

            if (query === lastSearchedQuery) return;

            indicator.classList.remove('is-visible');
            debounceTimer = setTimeout(() => {
                executeInternetSearch(query, input, indicator, popover);
            }, 480);
        });

        // Fecha ao pressionar Escape
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closePopover(popover);
            }
        });

        // Fecha ao clicar fora
        document.addEventListener('pointerdown', (e) => {
            if (popover.classList.contains('is-open')) {
                if (!wrapper.contains(e.target)) {
                    closePopover(popover);
                }
            }
        });
    }

    async function executeInternetSearch(query, input, indicator, popover) {
        if (currentAbortController) {
            currentAbortController.abort();
        }
        currentAbortController = new AbortController();

        indicator.classList.add('is-visible');
        lastSearchedQuery = query;

        try {
            const response = await fetch(`/ai/search-title/?q=${encodeURIComponent(query)}`, {
                signal: currentAbortController.signal,
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error(`Erro na busca: ${response.status}`);
            }

            const data = await response.json();
            indicator.classList.remove('is-visible');

            if (data.success && (data.total > 0 || (data.suggestion && data.suggestion.titulo))) {
                renderPopoverContent(data, input, popover);
                openPopover(popover);
            } else {
                closePopover(popover);
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.debug('Erro ao pesquisar título na internet:', err);
                indicator.classList.remove('is-visible');
            }
        }
    }

    function openPopover(popover) {
        popover.classList.add('is-open');
        activePopover = popover;
    }

    function closePopover(popover) {
        if (!popover) return;
        popover.classList.remove('is-open');
        if (activePopover === popover) activePopover = null;
    }

    function renderPopoverContent(data, input, popover) {
        const query = data.query;
        const suggestion = data.suggestion || {};
        const items = data.items || [];
        const total = data.total || items.length;

        const encodedQuery = encodeURIComponent(query);
        const mlSearchUrl = `https://lista.mercadolivre.com.br/${encodeURIComponent(query.replace(/\s+/g, '-'))}`;
        const amazonSearchUrl = `https://www.amazon.com.br/s?k=${encodedQuery}`;
        const googleSearchUrl = `https://www.google.com/search?q=${encodedQuery}+preco+brasil`;

        let html = `
            <div class="title-search-header">
                <div class="title-search-header-title">
                    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>
                    <span>Pesquisa na Internet: "<strong>${escapeHtml(query)}</strong>"</span>
                    <span class="title-search-count-badge">${total} produto(s)</span>
                </div>
                <button type="button" class="title-search-close-btn" title="Fechar sugestões (Esc)">
                    <svg viewBox="0 0 24 24"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>
                </button>
            </div>
        `;

        // Card de Sugestão Inteligente Consolidada
        if (suggestion.titulo) {
            const novoText = suggestion.preco_novo_formatado ? `Novo Ref: ${suggestion.preco_novo_formatado}` : '';
            const usadoText = suggestion.preco_usado_formatado ? `Usado Sugerido: ${suggestion.preco_usado_formatado}` : '';
            const catDisplay = suggestion.categoria_display || '';

            html += `
                <div class="title-search-smart-banner">
                    <div class="title-search-smart-info">
                        <div class="title-search-smart-title" title="${escapeHtml(suggestion.titulo)}">
                            <svg viewBox="0 0 24 24"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
                            <span>${escapeHtml(suggestion.titulo)}</span>
                        </div>
                        <div class="title-search-smart-pills">
                            ${novoText ? `<span class="title-search-price-pill">${novoText}</span>` : ''}
                            ${usadoText ? `<span class="title-search-price-pill" style="background:#fef3c7; color:#92400e;">${usadoText}</span>` : ''}
                            ${catDisplay ? `<span class="title-search-category-pill">🏷️ ${escapeHtml(catDisplay)}</span>` : ''}
                        </div>
                    </div>
                    <button type="button" class="title-search-apply-all-btn" id="btn-apply-all-smart">
                        <svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                        <span>Aplicar Tudo</span>
                    </button>
                </div>
            `;
        }

        // Lista de Itens Encontrados na Internet
        if (items.length > 0) {
            html += `<div class="title-search-list">`;
            items.forEach((item, idx) => {
                const title = item.title || 'Produto Web';
                const priceFmt = item.price_formatted || (item.price ? `R$ ${item.price}` : '');
                const source = item.source || 'Internet';
                const thumb = item.thumbnail;
                const link = item.url || '#';

                html += `
                    <div class="title-search-item" data-index="${idx}">
                        <div class="title-search-item-left">
                            ${thumb ? `<img src="${escapeHtml(thumb)}" alt="" class="title-search-thumb" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" /><div class="title-search-thumb-placeholder" style="display:none;"><svg viewBox="0 0 24 24"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect><circle cx="9" cy="9" r="2"></circle><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"></path></svg></div>` : `
                                <div class="title-search-thumb-placeholder">
                                    <svg viewBox="0 0 24 24"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect><circle cx="9" cy="9" r="2"></circle><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"></path></svg>
                                </div>
                            `}
                            <div class="title-search-item-details">
                                <span class="title-search-item-title" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
                                <div class="title-search-item-meta">
                                    <span class="title-search-source-tag">${escapeHtml(source)}</span>
                                    ${priceFmt ? `<span>•</span><span class="title-search-item-price">${escapeHtml(priceFmt)}</span>` : ''}
                                </div>
                            </div>
                        </div>
                        <div class="title-search-item-actions">
                            <button type="button" class="title-search-apply-item-btn" data-item-idx="${idx}" title="Preencher formulário com os dados deste anúncio">
                                <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                <span>Aplicar</span>
                            </button>
                            ${link && link !== '#' ? `
                                <a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer" class="title-search-link-btn" title="Abrir anúncio na web ↗">
                                    <svg viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                                </a>
                            ` : ''}
                        </div>
                    </div>
                `;
            });
            html += `</div>`;
        }

        // Rodapé com atalhos de busca
        html += `
            <div class="title-search-footer">
                <div class="title-search-shortcuts">
                    <span style="font-weight:600;">Ver mais:</span>
                    <a href="${googleSearchUrl}" target="_blank" rel="noopener noreferrer" class="title-search-shortcut-link" title="Pesquisar no Google">
                        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                        <span>Google ↗</span>
                    </a>
                    <a href="${mlSearchUrl}" target="_blank" rel="noopener noreferrer" class="title-search-shortcut-link" title="Pesquisar no Mercado Livre">
                        <svg viewBox="0 0 24 24"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>
                        <span>Mercado Livre ↗</span>
                    </a>
                    <a href="${amazonSearchUrl}" target="_blank" rel="noopener noreferrer" class="title-search-shortcut-link" title="Pesquisar na Amazon">
                        <svg viewBox="0 0 24 24"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
                        <span>Amazon ↗</span>
                    </a>
                </div>
                <span>Dica: clique em Aplicar para preencher campos</span>
            </div>
        `;

        popover.innerHTML = html;

        // Binds dos botões do popover
        const closeBtn = popover.querySelector('.title-search-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                closePopover(popover);
            });
        }

        const applyAllBtn = popover.querySelector('#btn-apply-all-smart');
        if (applyAllBtn) {
            applyAllBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                applySmartSuggestion(suggestion, input, popover);
            });
        }

        const applyItemBtns = popover.querySelectorAll('.title-search-apply-item-btn');
        applyItemBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.getAttribute('data-item-idx'), 10);
                const selectedItem = items[idx];
                if (selectedItem) {
                    applyIndividualItem(selectedItem, suggestion, input, popover);
                }
            });
        });
    }

    function applySmartSuggestion(suggestion, input, popover) {
        if (!suggestion) return;

        // 1. Título
        if (suggestion.titulo) {
            input.value = suggestion.titulo;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            updateSlugField(suggestion.titulo);
        }

        // 2. Preços (Django Admin)
        const precoNovoField = document.getElementById('id_preco_novo_referencia');
        if (precoNovoField && suggestion.preco_novo) {
            precoNovoField.value = suggestion.preco_novo.toFixed(2);
            precoNovoField.dispatchEvent(new Event('change', { bubbles: true }));
        }

        const precoUsadoField = document.getElementById('id_preco_usado');
        if (precoUsadoField && suggestion.preco_usado) {
            precoUsadoField.value = suggestion.preco_usado.toFixed(2);
            precoUsadoField.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // 3. Categoria
        if (suggestion.categoria) {
            const catField = document.getElementById('id_categoria') || document.getElementById('categoria');
            if (catField) {
                catField.value = suggestion.categoria;
                catField.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        // 4. URLs de Referência (Django Admin)
        if (suggestion.urls && suggestion.urls.length > 0) {
            appendReferenceUrls(suggestion.urls);
        }

        closePopover(popover);
        notifyUser('✓ Dados completos da internet aplicados ao formulário!');
    }

    function applyIndividualItem(item, suggestion, input, popover) {
        // 1. Título
        if (item.title) {
            input.value = item.title;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            updateSlugField(item.title);
        }

        // 2. Preço Novo Referência (se o item tem preço)
        if (item.price) {
            const precoNovoField = document.getElementById('id_preco_novo_referencia');
            if (precoNovoField) {
                precoNovoField.value = Number(item.price).toFixed(2);
                precoNovoField.dispatchEvent(new Event('change', { bubbles: true }));
            }

            // Sugere ~60% para usado se vazio
            const precoUsadoField = document.getElementById('id_preco_usado');
            if (precoUsadoField && (!precoUsadoField.value || precoUsadoField.value === '0.00')) {
                precoUsadoField.value = (Number(item.price) * 0.6).toFixed(2);
                precoUsadoField.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        // 3. Categoria da sugestão inteligente
        if (suggestion && suggestion.categoria) {
            const catField = document.getElementById('id_categoria') || document.getElementById('categoria');
            if (catField) {
                catField.value = suggestion.categoria;
                catField.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        // 4. URL do item
        if (item.url && item.url.startsWith('http')) {
            appendReferenceUrls([item.url]);
        }

        closePopover(popover);
        notifyUser(`✓ Item "${item.title.substring(0, 30)}..." aplicado ao formulário!`);
    }

    function updateSlugField(title) {
        const slugField = document.getElementById('id_slug');
        if (slugField && (!slugField.value || slugField.dataset.autoSlug !== 'false')) {
            const slug = title
                .toLowerCase()
                .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
                .replace(/[^a-z0-9\s-]/g, '')
                .trim()
                .replace(/\s+/g, '-')
                .replace(/-+/g, '-')
                .substring(0, 50);
            slugField.value = slug;
            slugField.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function appendReferenceUrls(newUrls) {
        const urlsField = document.getElementById('id_urls_referencia');
        if (!urlsField) return;

        try {
            let currentList = [];
            const rawVal = urlsField.value.trim();
            if (rawVal) {
                if (rawVal.startsWith('[') && rawVal.endsWith(']')) {
                    currentList = JSON.parse(rawVal);
                } else {
                    currentList = rawVal.split('\n').map(u => u.trim()).filter(Boolean);
                }
            }

            if (!Array.isArray(currentList)) currentList = [];

            newUrls.forEach(u => {
                if (u && u.startsWith('http') && !currentList.includes(u)) {
                    currentList.push(u);
                }
            });

            urlsField.value = JSON.stringify(currentList, null, 2);
            urlsField.dispatchEvent(new Event('change', { bubbles: true }));
        } catch (e) {
            // Em caso de falha no JSON, concatena como texto
            urlsField.value = JSON.stringify(newUrls, null, 2);
            urlsField.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function notifyUser(message) {
        // Usa o sistema de toasts de admin_subtle_actions.js se disponível
        let container = document.getElementById('admin-subtle-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'admin-subtle-toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = 'admin-subtle-toast';
        toast.innerHTML = `
            <svg viewBox="0 0 24 24" style="width:15px; height:15px; stroke:#4ade80; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"><polyline points="20 6 9 17 4 12"></polyline></svg>
            <span>${escapeHtml(message)}</span>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-hide');
            setTimeout(() => toast.remove(), 250);
        }, 3200);
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
})();
