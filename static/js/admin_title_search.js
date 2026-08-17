/**
 * Live Title Internet Search & Smart Form Auto-Populate - Hub de Desapego
 * Dispara pesquisa na internet em tempo real ao digitar nomes no campo de título.
 * Permite selecionar e aplicar fotos da web, categoria, pretensão, preços e descrição estruturada.
 * Padrão de ícones de linha (stroke-width: 1.8) e botões sutis idênticos a admin_subtle_actions.css.
 */

(function () {
    'use strict';

    let currentAbortController = null;
    let debounceTimer = null;
    let activePopover = null;
    let lastSearchedQuery = '';
    let isApplying = false;

    const CATEGORIES = [
        { value: 'eletronicos', label: 'Eletrônicos e Informática' },
        { value: 'moveis', label: 'Móveis e Decoração' },
        { value: 'eletrodomesticos', label: 'Eletrodomésticos' },
        { value: 'ferramentas', label: 'Ferramentas e Casa' },
        { value: 'instrumentos', label: 'Instrumentos Musicais' },
        { value: 'vestuario', label: 'Roupas e Acessórios' },
        { value: 'esportes', label: 'Esportes e Lazer' },
        { value: 'livros', label: 'Livros e Colecionáveis' },
        { value: 'outros', label: 'Outros' }
    ];

    const AD_TYPES = [
        { value: 'venda', label: 'Venda' },
        { value: 'aluguel', label: 'Aluguel' },
        { value: 'ambos', label: 'Venda e Aluguel' }
    ];

    document.addEventListener('DOMContentLoaded', () => {
        initTitleSearch();
    });

    function getDebounceDelay() {
        if (window.TITLE_SEARCH_CONFIG && typeof window.TITLE_SEARCH_CONFIG.debounceSeconds !== 'undefined') {
            const sec = parseFloat(window.TITLE_SEARCH_CONFIG.debounceSeconds);
            if (!isNaN(sec)) return sec;
        }
        return 2.0; // Padrão 2.0 segundos
    }

    function initTitleSearch() {
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

        // Cria botão/ícone sutil de busca com metamorfose de linha para spinner circular
        const searchBtn = document.createElement('button');
        searchBtn.type = 'button';
        searchBtn.className = 'title-search-btn';
        searchBtn.setAttribute('aria-label', 'Pesquisar produto na internet');
        
        const debounceSec = getDebounceDelay();
        if (debounceSec === 0) {
            searchBtn.title = 'Pesquisar produto na internet (busca automática desativada - clique para buscar)';
        } else {
            searchBtn.title = `Pesquisar produto na internet (${debounceSec.toFixed(1)}s sem digitar ou clique)`;
        }

        searchBtn.innerHTML = `
            <svg viewBox="0 0 24 24">
                <circle class="title-search-svg-circle" cx="11" cy="11" r="7.5"></circle>
                <path class="title-search-svg-handle" d="m21 21-4.35-4.35"></path>
            </svg>
        `;
        wrapper.appendChild(searchBtn);

        // Cria o popover flutuante
        const popover = document.createElement('div');
        popover.className = 'title-search-popover';
        wrapper.appendChild(popover);

        // Disparo manual ao clicar no ícone
        searchBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const query = input.value.trim();
            if (query.length >= 3) {
                if (debounceTimer) clearTimeout(debounceTimer);
                executeInternetSearch(query, input, searchBtn, popover, true);
            } else {
                input.focus();
            }
        });

        // Escuta digitação com debounce configurável
        input.addEventListener('input', (e) => {
            if (isApplying) return;

            const query = e.target.value.trim();

            if (debounceTimer) clearTimeout(debounceTimer);

            if (query.length < 3) {
                searchBtn.classList.remove('is-loading');
                closePopover(popover);
                lastSearchedQuery = '';
                return;
            }

            if (query === lastSearchedQuery) return;

            const currentDelay = getDebounceDelay();
            if (currentDelay <= 0) {
                // Busca automática desativada (0s). Permite busca apenas manual por clique ou Enter.
                return;
            }

            debounceTimer = setTimeout(() => {
                executeInternetSearch(query, input, searchBtn, popover, false);
            }, Math.round(currentDelay * 1000));
        });

        // Dispara com Enter ou fecha com Escape
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const query = input.value.trim();
                if (query.length >= 3) {
                    e.preventDefault();
                    if (debounceTimer) clearTimeout(debounceTimer);
                    executeInternetSearch(query, input, searchBtn, popover, true);
                }
            } else if (e.key === 'Escape') {
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

    async function executeInternetSearch(query, input, searchBtn, popover, force = false) {
        if (isApplying) return;
        if (!force && query === lastSearchedQuery && popover.classList.contains('is-open')) return;

        if (currentAbortController) {
            currentAbortController.abort();
        }
        currentAbortController = new AbortController();

        searchBtn.classList.add('is-loading');
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
            searchBtn.classList.remove('is-loading');

            if (data.success && (data.total > 0 || (data.suggestion && data.suggestion.titulo))) {
                renderPopoverContent(data, input, popover);
                openPopover(popover);
            } else {
                closePopover(popover);
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.debug('Erro ao pesquisar título na internet:', err);
                searchBtn.classList.remove('is-loading');
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
        const images = suggestion.images || [];

        const encodedQuery = encodeURIComponent(query);
        const mlSearchUrl = `https://lista.mercadolivre.com.br/${encodeURIComponent(query.replace(/\s+/g, '-'))}`;
        const amazonSearchUrl = `https://www.amazon.com.br/s?k=${encodedQuery}`;
        const googleSearchUrl = `https://www.google.com/search?q=${encodedQuery}+preco+brasil`;

        let html = `
            <div class="title-search-header">
                <div class="title-search-header-title">
                    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>
                    <span>Pesquisa na Internet: "<strong>${escapeHtml(query)}</strong>"</span>
                    <span class="title-search-count-badge">${total} resultado(s)</span>
                </div>
                <button type="button" class="title-search-close-btn" title="Fechar sugestões (Esc)">
                    <svg viewBox="0 0 24 24"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>
                </button>
            </div>
        `;

        // Painel Principal de Configuração e Aplicação de Dados
        if (suggestion.titulo) {
            const currentCat = suggestion.categoria || 'outros';
            const currentTipo = suggestion.tipo_anuncio || 'venda';
            const precoNovoVal = suggestion.preco_novo ? Number(suggestion.preco_novo).toFixed(2) : '';
            const precoUsadoVal = suggestion.preco_usado ? Number(suggestion.preco_usado).toFixed(2) : '';

            html += `
                <div class="title-search-smart-panel">
                    <div class="title-search-smart-header">
                        <div class="title-search-smart-title" title="${escapeHtml(suggestion.titulo)}">
                            <svg viewBox="0 0 24 24"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>
                            <span>${escapeHtml(suggestion.titulo)}</span>
                        </div>
                    </div>

                    <!-- Configurações de Categoria, Pretensão e Preços -->
                    <div class="title-search-fields-grid">
                        <div class="title-search-field-item">
                            <label class="title-search-field-label">
                                <svg viewBox="0 0 24 24"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>
                                <span>Categoria</span>
                            </label>
                            <select id="smart-apply-category" class="title-search-field-select">
                                ${CATEGORIES.map(c => `<option value="${c.value}" ${c.value === currentCat ? 'selected' : ''}>${c.label}</option>`).join('')}
                            </select>
                        </div>

                        <div class="title-search-field-item">
                            <label class="title-search-field-label">
                                <svg viewBox="0 0 24 24"><rect width="20" height="14" x="2" y="7" rx="2" ry="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path></svg>
                                <span>Pretensão</span>
                            </label>
                            <select id="smart-apply-tipo" class="title-search-field-select">
                                ${AD_TYPES.map(t => `<option value="${t.value}" ${t.value === currentTipo ? 'selected' : ''}>${t.label}</option>`).join('')}
                            </select>
                        </div>

                        <div class="title-search-field-item">
                            <label class="title-search-field-label">
                                <span>💰 Preço Novo Ref. (R$)</span>
                            </label>
                            <input type="number" step="0.01" id="smart-apply-preco-novo" class="title-search-field-input" value="${precoNovoVal}" placeholder="Ex: 899.00">
                        </div>

                        <div class="title-search-field-item">
                            <label class="title-search-field-label">
                                <span>🏷️ Preço Usado (R$)</span>
                            </label>
                            <input type="number" step="0.01" id="smart-apply-preco-usado" class="title-search-field-input" value="${precoUsadoVal}" placeholder="Ex: 540.00">
                        </div>
                    </div>

                    <!-- Seção de Seleção de Fotos Encontradas na Web -->
                    ${images.length > 0 ? `
                        <div class="title-search-photos-section">
                            <div class="title-search-photos-header">
                                <span>📸 Fotos da Internet (<span id="selected-photos-count">${images.length}</span>/${images.length} selecionadas)</span>
                                <button type="button" class="title-search-photos-toggle-btn" id="btn-toggle-all-photos">Alternar Seleção</button>
                            </div>
                            <div class="title-search-photos-grid" id="smart-photos-container">
                                ${images.map((imgUrl, i) => `
                                    <div class="title-search-photo-card is-selected" data-photo-url="${escapeHtml(imgUrl)}" title="Clique para selecionar ou desmarcar esta foto">
                                        <img src="${escapeHtml(imgUrl)}" alt="Foto ${i + 1}" loading="lazy" />
                                        <div class="title-search-photo-check">
                                            <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    <!-- Seção de Descrição Gerada / Ficha Técnica -->
                    ${suggestion.descricao ? `
                        <div class="title-search-desc-section">
                            <div class="title-search-desc-header" id="smart-desc-toggle">
                                <span class="title-search-desc-toggle-label">
                                    <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                                    <span>Visualizar Descrição e Ficha Técnica Sugerida</span>
                                </span>
                                <label style="display:flex; align-items:center; gap:4px; font-size:11px; font-weight:600; color:#166534; cursor:pointer;" onclick="event.stopPropagation();">
                                    <input type="checkbox" id="smart-apply-desc-checkbox" checked style="accent-color:#16a34a;" />
                                    <span>Aplicar descrição</span>
                                </label>
                            </div>
                            <div class="title-search-desc-preview-body" id="smart-desc-preview-body" style="display:none;">${escapeHtml(suggestion.descricao)}</div>
                        </div>
                    ` : ''}

                    <!-- Botão de Ação Principal -->
                    <button type="button" class="title-search-apply-all-btn" id="btn-apply-all-smart">
                        <svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                        <span id="btn-apply-all-text">⚡ Aplicar Tudo no Formulário</span>
                    </button>
                </div>
            `;
        }

        // Lista de Anúncios Web Específicos
        if (items.length > 0) {
            html += `
                <div class="title-search-list-section">
                    <div class="title-search-list-title">Anúncios e referências encontradas na web:</div>
                    <div class="title-search-list">
            `;
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
                            <button type="button" class="title-search-apply-item-btn" data-item-idx="${idx}" title="Preencher formulário com este anúncio">
                                <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                <span>Usar este</span>
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
            html += `</div></div>`;
        }

        // Rodapé com atalhos de busca rápida
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
                <span>Dica: clique em Aplicar Tudo para preencher o formulário</span>
            </div>
        `;

        popover.innerHTML = html;

        // Binds dos elementos
        const closeBtn = popover.querySelector('.title-search-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                closePopover(popover);
            });
        }

        // Toggle de seleção de fotos
        const photoCards = popover.querySelectorAll('.title-search-photo-card');
        const photoCountSpan = popover.querySelector('#selected-photos-count');
        const updatePhotoCount = () => {
            const selected = popover.querySelectorAll('.title-search-photo-card.is-selected').length;
            if (photoCountSpan) photoCountSpan.textContent = selected;
        };

        photoCards.forEach(card => {
            card.addEventListener('click', (e) => {
                e.stopPropagation();
                card.classList.toggle('is-selected');
                updatePhotoCount();
            });
        });

        const toggleAllPhotosBtn = popover.querySelector('#btn-toggle-all-photos');
        if (toggleAllPhotosBtn) {
            toggleAllPhotosBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const anySelected = popover.querySelectorAll('.title-search-photo-card.is-selected').length > 0;
                photoCards.forEach(c => {
                    if (anySelected) {
                        c.classList.remove('is-selected');
                    } else {
                        c.classList.add('is-selected');
                    }
                });
                updatePhotoCount();
            });
        }

        // Toggle de visualização da descrição
        const descToggle = popover.querySelector('#smart-desc-toggle');
        const descPreviewBody = popover.querySelector('#smart-desc-preview-body');
        if (descToggle && descPreviewBody) {
            descToggle.addEventListener('click', () => {
                descPreviewBody.style.display = descPreviewBody.style.display === 'none' ? 'block' : 'none';
            });
        }

        // Botão de Aplicar Tudo com Seleções
        const applyAllBtn = popover.querySelector('#btn-apply-all-smart');
        if (applyAllBtn) {
            applyAllBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await handleApplyAll(suggestion, input, popover);
            });
        }

        // Botões de Usar Anúncio Individual
        const applyItemBtns = popover.querySelectorAll('.title-search-apply-item-btn');
        applyItemBtns.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.getAttribute('data-item-idx'), 10);
                const selectedItem = items[idx];
                if (selectedItem) {
                    await handleApplyIndividualItem(selectedItem, suggestion, input, popover);
                }
            });
        });
    }

    async function handleApplyAll(suggestion, input, popover) {
        const btn = popover.querySelector('#btn-apply-all-smart');
        const btnText = popover.querySelector('#btn-apply-all-text');

        if (btn) {
            btn.classList.add('is-loading');
            if (btnText) btnText.textContent = 'Aplicando dados e fotos...';
        }

        isApplying = true;

        try {
            // 1. Título
            const finalTitle = suggestion.titulo || input.value;
            input.value = finalTitle;
            lastSearchedQuery = finalTitle;
            input.dispatchEvent(new Event('change', { bubbles: true }));
            updateSlugField(finalTitle);

            // 2. Categoria selecionada
            const catSelect = popover.querySelector('#smart-apply-category');
            const selectedCategory = catSelect ? catSelect.value : suggestion.categoria;
            if (selectedCategory) {
                const catField = document.getElementById('id_categoria') || document.getElementById('categoria');
                if (catField) {
                    catField.value = selectedCategory;
                    catField.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }

            // 3. Pretensão selecionada
            const tipoSelect = popover.querySelector('#smart-apply-tipo');
            const selectedTipo = tipoSelect ? tipoSelect.value : (suggestion.tipo_anuncio || 'venda');
            if (selectedTipo) {
                const tipoField = document.getElementById('id_tipo_anuncio') || document.getElementById('tipo_anuncio');
                if (tipoField) {
                    tipoField.value = selectedTipo;
                    tipoField.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }

            // 4. Preços
            const precoNovoInput = popover.querySelector('#smart-apply-preco-novo');
            const precoNovoVal = precoNovoInput && precoNovoInput.value ? parseFloat(precoNovoInput.value) : suggestion.preco_novo;
            if (precoNovoVal) {
                const precoNovoField = document.getElementById('id_preco_novo_referencia');
                if (precoNovoField) {
                    precoNovoField.value = Number(precoNovoVal).toFixed(2);
                    precoNovoField.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }

            const precoUsadoInput = popover.querySelector('#smart-apply-preco-usado');
            const precoUsadoVal = precoUsadoInput && precoUsadoInput.value ? parseFloat(precoUsadoInput.value) : suggestion.preco_usado;
            if (precoUsadoVal) {
                const precoUsadoField = document.getElementById('id_preco_usado');
                if (precoUsadoField) {
                    precoUsadoField.value = Number(precoUsadoVal).toFixed(2);
                    precoUsadoField.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }

            // 5. Descrição / Ficha Técnica
            const descCheckbox = popover.querySelector('#smart-apply-desc-checkbox');
            const applyDesc = !descCheckbox || descCheckbox.checked;
            if (applyDesc && suggestion.descricao) {
                // No Django Admin e Upload Rápido (campo id_descricao_ia)
                const descIaField = document.getElementById('id_descricao_ia');
                if (descIaField) {
                    descIaField.value = suggestion.descricao;
                    descIaField.dispatchEvent(new Event('change', { bubbles: true }));
                    if (typeof window.updateAdminMarkdownPreviews === 'function') {
                        window.updateAdminMarkdownPreviews();
                    }
                }
            }

            // 6. URLs de Referência
            if (suggestion.urls && suggestion.urls.length > 0) {
                appendReferenceUrls(suggestion.urls);
            }

            // 7. Importação de Fotos Selecionadas
            const selectedPhotoCards = popover.querySelectorAll('.title-search-photo-card.is-selected');
            const selectedPhotoUrls = Array.from(selectedPhotoCards).map(c => c.getAttribute('data-photo-url')).filter(Boolean);

            let photosImported = 0;
            if (selectedPhotoUrls.length > 0) {
                photosImported = await importPhotos(selectedPhotoUrls, finalTitle);
            }

            closePopover(popover);

            const msgParts = ['✓ Dados aplicados'];
            if (selectedCategory) msgParts.push('categoria');
            if (selectedTipo) msgParts.push('pretensão');
            if (applyDesc) msgParts.push('descrição');
            if (photosImported > 0) msgParts.push(`${photosImported} foto(s)`);

            notifyUser(`${msgParts.join(', ')} preenchidos com sucesso!`);

        } catch (err) {
            console.error('Erro ao aplicar sugestões:', err);
            notifyUser('Dados parciais aplicados.', true);
        } finally {
            setTimeout(() => {
                isApplying = false;
            }, 300);
        }
    }

    async function handleApplyIndividualItem(item, suggestion, input, popover) {
        isApplying = true;

        try {
            // 1. Título
            const itemTitle = item.title || input.value;
            input.value = itemTitle;
            lastSearchedQuery = itemTitle;
            input.dispatchEvent(new Event('change', { bubbles: true }));
            updateSlugField(itemTitle);

            // 2. Preços
            if (item.price) {
                const precoNovoField = document.getElementById('id_preco_novo_referencia');
                if (precoNovoField) {
                    precoNovoField.value = Number(item.price).toFixed(2);
                    precoNovoField.dispatchEvent(new Event('change', { bubbles: true }));
                }

                const precoUsadoField = document.getElementById('id_preco_usado');
                if (precoUsadoField && (!precoUsadoField.value || precoUsadoField.value === '0.00')) {
                    precoUsadoField.value = (Number(item.price) * 0.6).toFixed(2);
                    precoUsadoField.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }

            // 3. Categoria
            if (suggestion && suggestion.categoria) {
                const catField = document.getElementById('id_categoria') || document.getElementById('categoria');
                if (catField) {
                    catField.value = suggestion.categoria;
                    catField.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }

            // 4. Pretensão
            const tipoField = document.getElementById('id_tipo_anuncio') || document.getElementById('tipo_anuncio');
            if (tipoField && !tipoField.value) {
                tipoField.value = 'venda';
                tipoField.dispatchEvent(new Event('change', { bubbles: true }));
            }

            // 5. Descrição
            if (suggestion && suggestion.descricao) {
                const descIaField = document.getElementById('id_descricao_ia');
                if (descIaField && !descIaField.value) {
                    descIaField.value = suggestion.descricao;
                    descIaField.dispatchEvent(new Event('change', { bubbles: true }));
                    if (typeof window.updateAdminMarkdownPreviews === 'function') {
                        window.updateAdminMarkdownPreviews();
                    }
                }
            }

            // 6. URL do item
            if (item.url && item.url.startsWith('http')) {
                appendReferenceUrls([item.url]);
            }

            // 7. Foto do item (se houver thumbnail)
            let photosImported = 0;
            if (item.thumbnail && item.thumbnail.startsWith('http')) {
                photosImported = await importPhotos([item.thumbnail], itemTitle);
            }

            closePopover(popover);
            notifyUser(`✓ Item "${itemTitle.substring(0, 32)}..." aplicado ao formulário!`);

        } catch (err) {
            console.error('Erro ao aplicar anúncio individual:', err);
        } finally {
            setTimeout(() => {
                isApplying = false;
            }, 300);
        }
    }

    async function importPhotos(photoUrls, baseTitle) {
        let count = 0;

        // Caso 1: Formulário de Upload Rápido (IndexedDB PhotoDraftStorage)
        if (typeof PhotoDraftStorage !== 'undefined' && typeof window.refreshPhotosFromDB === 'function') {
            const currentPhotos = await PhotoDraftStorage.getAllPhotos();
            const hasCover = currentPhotos.some(p => p.isCover);

            for (let i = 0; i < photoUrls.length; i++) {
                const url = photoUrls[i];
                try {
                    const proxyUrl = `/ai/proxy-image/?url=${encodeURIComponent(url)}`;
                    const resp = await fetch(proxyUrl);
                    if (resp.ok) {
                        const blob = await resp.blob();
                        const isFirst = (currentPhotos.length === 0 && i === 0) || (!hasCover && i === 0);
                        const cleanName = `web_foto_${Date.now()}_${i + 1}.jpg`;
                        const file = new File([blob], cleanName, { type: blob.type || 'image/jpeg' });
                        await PhotoDraftStorage.savePhoto(file, isFirst);
                        count++;
                    }
                } catch (e) {
                    console.warn(`Erro ao baixar foto remota ${url}:`, e);
                }
            }

            if (count > 0) {
                await window.refreshPhotosFromDB();
            }
            return count;
        }

        // Caso 2: Django Admin - se já estiver editando um item existente com ID
        const itemId = getItemIdFromPage();
        if (itemId) {
            try {
                const csrfToken = getCsrfToken();
                const resp = await fetch('/ai/import-web-images/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ item_id: itemId, images: photoUrls })
                });
                if (resp.ok) {
                    const data = await resp.json();
                    if (data.success) {
                        count = data.imported || photoUrls.length;
                    }
                }
            } catch (e) {
                console.warn('Erro ao importar fotos no Django Admin:', e);
            }
        }

        return count;
    }

    function getItemIdFromPage() {
        const match = window.location.pathname.match(/\/admin\/core\/item\/(\d+)\/change\//);
        return match ? match[1] : null;
    }

    function getCsrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input && input.value) return input.value;
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
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
                .substring(0, 60);
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
            urlsField.value = JSON.stringify(newUrls, null, 2);
            urlsField.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function notifyUser(message, isError = false) {
        let container = document.getElementById('admin-subtle-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'admin-subtle-toast-container';
            document.body.appendChild(container);
        }

        const iconSvg = isError
            ? '<svg viewBox="0 0 24 24" style="width:15px; height:15px; stroke:#f87171; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
            : '<svg viewBox="0 0 24 24" style="width:15px; height:15px; stroke:#4ade80; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round;"><polyline points="20 6 9 17 4 12"></polyline></svg>';

        const toast = document.createElement('div');
        toast.className = `admin-subtle-toast ${isError ? 'toast-error' : ''}`;
        toast.innerHTML = `
            ${iconSvg}
            <span>${escapeHtml(message)}</span>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-hide');
            setTimeout(() => toast.remove(), 250);
        }, 3600);
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
