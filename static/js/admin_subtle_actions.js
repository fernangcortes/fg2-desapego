/**
 * Django Admin Subtle Quick Actions & Inline Delete Confirmation - Hub de Desapego
 * Line icons sutis, sem caixas/modais, com confirmação inline e animação fluida.
 */

(function () {
    'use strict';

    let activeConfirmingBtn = null;
    let resetTimer = null;

    document.addEventListener('DOMContentLoaded', () => {
        initSubtleActions();
        loadSerpApiQuota();
    });

    function initSubtleActions() {
        document.addEventListener('click', (e) => {
            const deleteBtn = e.target.closest('.admin-delete-action-btn');
            if (deleteBtn) {
                e.preventDefault();
                e.stopPropagation();
                handleDeleteClick(deleteBtn);
                return;
            }

            const lensBtn = e.target.closest('.admin-lens-btn');
            if (lensBtn) {
                e.preventDefault();
                e.stopPropagation();
                handleLensClick(lensBtn);
                return;
            }

            // Clique fora: cancela qualquer confirmação ativa
            if (activeConfirmingBtn && !e.target.closest('.admin-delete-action-btn')) {
                resetConfirmState(activeConfirmingBtn);
            }
        });

        // Tecla Escape cancela confirmação
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && activeConfirmingBtn) {
                resetConfirmState(activeConfirmingBtn);
            }
        });
    }

    function handleDeleteClick(btn) {
        // Se já está processando a exclusão, ignora cliques adicionais
        if (btn.classList.contains('is-deleting')) return;

        // 1º Clique: Ativa estado de confirmação inline
        if (!btn.classList.contains('is-confirming')) {
            if (activeConfirmingBtn && activeConfirmingBtn !== btn) {
                resetConfirmState(activeConfirmingBtn);
            }

            btn.classList.add('is-confirming');
            btn.setAttribute('title', 'Clique novamente para confirmar a exclusão');
            activeConfirmingBtn = btn;

            // Auto-cancela após 3.5 segundos se não houver o 2º clique
            if (resetTimer) clearTimeout(resetTimer);
            resetTimer = setTimeout(() => {
                if (btn.classList.contains('is-confirming')) {
                    resetConfirmState(btn);
                }
            }, 3500);
            return;
        }

        // 2º Clique: Confirmação realizada, dispara exclusão assíncrona
        if (resetTimer) clearTimeout(resetTimer);
        executeDelete(btn);
    }

    function resetConfirmState(btn) {
        if (!btn) return;
        btn.classList.remove('is-confirming');
        btn.classList.remove('is-deleting');
        btn.setAttribute('title', 'Excluir este item');
        if (activeConfirmingBtn === btn) {
            activeConfirmingBtn = null;
        }
    }

    async function executeDelete(btn) {
        const deleteUrl = btn.getAttribute('data-delete-url');
        const itemId = btn.getAttribute('data-item-id');
        const itemTitle = btn.getAttribute('data-item-title') || 'Item';
        const csrfToken = getCsrfToken();

        btn.classList.add('is-deleting');

        try {
            const response = await fetch(deleteUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ item_id: itemId })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Erro ${response.status}: Falha ao excluir`);
            }

            const data = await response.json();

            // Animação fluida de remoção da linha na tabela
            const tr = btn.closest('tr');
            if (tr) {
                tr.classList.add('row-deleting-anim');

                setTimeout(() => {
                    tr.classList.add('row-collapse-anim');
                    setTimeout(() => {
                        tr.remove();
                        updateTableCount();
                    }, 200);
                }, 320);
            }

            activeConfirmingBtn = null;
            showAdminSubtleToast(data.message || `Item '${itemTitle}' excluído com sucesso.`);

        } catch (err) {
            console.error('Erro na exclusão rápida:', err);
            resetConfirmState(btn);
            showAdminSubtleToast(err.message || 'Não foi possível excluir o item.', true);
        }
    }

    function updateTableCount() {
        const countSpan = document.querySelector('.paginator, .small.quiet, .actions span.all');
        const remainingRows = document.querySelectorAll('#result_list tbody tr');
        if (remainingRows.length === 0) {
            const tbody = document.querySelector('#result_list tbody');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="20" style="text-align: center; padding: 2rem; color: #94a3b8;">Nenhum item encontrado.</td></tr>';
            }
        }
    }

    function handleLensClick(btn) {
        const relativeUrl = btn.getAttribute('data-image-url');
        if (!relativeUrl) return;

        // Monta a URL pública absoluta
        const fullUrl = window.location.origin + relativeUrl;
        const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        const lensUrl = isLocalhost 
            ? 'https://lens.google.com/' 
            : `https://lens.google.com/uploadbyurl?url=${encodeURIComponent(fullUrl)}`;

        // Abre a nova aba IMEDIATAMENTE (sincronamente) para evitar bloqueio de popup do navegador
        const newWindow = window.open(lensUrl, '_blank', 'noopener,noreferrer');
        if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
            // Se bloqueado pelo navegador, fallback para link direto
            window.location.href = lensUrl;
        }

        showAdminSubtleToast('🔍 Abrindo Google Lens...', false, '🔍');

        // Copia a imagem ou URL para a área de transferência em segundo plano
        (async () => {
            try {
                if (navigator.clipboard && window.fetch) {
                    const imgResp = await fetch(relativeUrl);
                    const blob = await imgResp.blob();
                    if (window.ClipboardItem) {
                        const pngBlob = blob.type === 'image/png' ? blob : new Blob([blob], { type: 'image/png' });
                        await navigator.clipboard.write([
                            new ClipboardItem({ 'image/png': pngBlob })
                        ]);
                        showAdminSubtleToast('✓ Foto copiada! Se desejar, cole (Ctrl+V) no Google Lens.', false, '📋');
                    } else {
                        await navigator.clipboard.writeText(fullUrl);
                    }
                }
            } catch (e) {
                try {
                    if (navigator.clipboard) {
                        await navigator.clipboard.writeText(fullUrl);
                    }
                } catch (_) {}
            }
        })();
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

    function showAdminSubtleToast(message, isError = false, customIconSvg = '') {
        let container = document.getElementById('admin-subtle-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'admin-subtle-toast-container';
            document.body.appendChild(container);
        }

        const iconSvg = isError 
            ? '<svg viewBox="0 0 24 24" style="width:15px; height:15px; stroke:#f87171; fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
            : (customIconSvg || '<svg viewBox="0 0 24 24" style="width:15px; height:15px; stroke:#4ade80; fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round;"><polyline points="20 6 9 17 4 12"></polyline></svg>');

        const toast = document.createElement('div');
        toast.className = `admin-subtle-toast ${isError ? 'toast-error' : ''}`;
        toast.innerHTML = `
            ${iconSvg}
            <span>${message}</span>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-hide');
            setTimeout(() => toast.remove(), 250);
        }, 3500);
    }

    /* ==========================================================================
       Admin Markdown Live Formatter (Descrição Sugerida por IA & Manual)
       ========================================================================== */

    function parseMarkdownToHtml(md) {
        if (!md || typeof md !== 'string' || !md.trim()) {
            return '<p class="admin-md-empty-hint"><em>Nenhuma descrição gerada por IA ainda. Digite o Markdown no editor à direita ou execute a análise de IA acima.</em></p>';
        }

        let text = md;

        // 1. Remove qualquer marcação de imagem Markdown ![...](...) e tags HTML <img>
        text = text.replace(/!\[.*?\]\(.*?\)/g, '');
        text = text.replace(/<img[^>]*>/g, '');

        // 2. Normaliza marcadores de tópicos unicode
        text = text.replace(/^[ \t]*[•●▪][ \t]+/gm, '- ');

        // 3. Limpa asteriscos redundantes dentro de títulos (ex: ## **Título** -> ## Título)
        text = text.replace(/^(#{1,6}[ \t]+)\*\*(.*?)\*\*/gm, '$1$2');

        const escapeHtml = (str) =>
            str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

        const inlineFormat = (str) => {
            // Negrito **texto** ou __texto__
            str = str.replace(/(\*\*|__)(.*?)\1/g, '<strong>$2</strong>');
            // Tachado ~~texto~~
            str = str.replace(/~~(.*?)~~/g, '<del>$1</del>');
            // Itálico *texto* ou _texto_
            str = str.replace(/(\*|_)(.*?)\1/g, '<em>$2</em>');
            // Código `code`
            str = str.replace(/`([^`]+)`/g, '<code>$1</code>');
            // Links [texto](url) -> texto destacado
            str = str.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="admin-md-link">$1</a>');
            return str;
        };

        const lines = text.split(/\r?\n/);
        let html = '';
        let inList = false;
        let listType = '';

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trimEnd();

            // Divisor horizontal (--- ou ***)
            if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
                if (inList) { html += listType === 'ol' ? '</ol>' : '</ul>'; inList = false; }
                html += '<hr class="admin-md-hr" />';
                continue;
            }

            // Blockquote (> texto)
            const quoteMatch = line.match(/^>\s*(.*)$/);
            if (quoteMatch) {
                if (inList) { html += listType === 'ol' ? '</ol>' : '</ul>'; inList = false; }
                html += `<blockquote class="admin-md-quote">${inlineFormat(escapeHtml(quoteMatch[1]))}</blockquote>`;
                continue;
            }

            // Cabeçalhos (#, ##, ###, ####, #####, ######)
            const headerMatch = line.match(/^(#{1,6})\s+(.*)$/);
            if (headerMatch) {
                if (inList) { html += listType === 'ol' ? '</ol>' : '</ul>'; inList = false; }
                const level = Math.min(headerMatch[1].length, 6);
                const content = inlineFormat(escapeHtml(headerMatch[2]));
                html += `<h${level} class="admin-md-h${level}">${content}</h${level}>`;
                continue;
            }

            // Itens de lista não ordenada (- item ou * item ou + item)
            const ulMatch = line.match(/^[-*+]\s+(.*)$/);
            if (ulMatch) {
                if (!inList || listType !== 'ul') {
                    if (inList) html += listType === 'ol' ? '</ol>' : '</ul>';
                    html += '<ul class="admin-md-ul">';
                    inList = true;
                    listType = 'ul';
                }
                html += `<li>${inlineFormat(escapeHtml(ulMatch[1]))}</li>`;
                continue;
            }

            // Itens de lista ordenada (1. item)
            const olMatch = line.match(/^\d+\.\s+(.*)$/);
            if (olMatch) {
                if (!inList || listType !== 'ol') {
                    if (inList) html += listType === 'ol' ? '</ol>' : '</ul>';
                    html += '<ol class="admin-md-ol">';
                    inList = true;
                    listType = 'ol';
                }
                html += `<li>${inlineFormat(escapeHtml(olMatch[1]))}</li>`;
                continue;
            }

            // Linha vazia
            if (!line.trim()) {
                if (inList) {
                    html += listType === 'ol' ? '</ol>' : '</ul>';
                    inList = false;
                }
                continue;
            }

            // Parágrafo normal
            if (inList) {
                html += listType === 'ol' ? '</ol>' : '</ul>';
                inList = false;
            }
            html += `<p class="admin-md-p">${inlineFormat(escapeHtml(line))}</p>`;
        }

        if (inList) {
            html += listType === 'ol' ? '</ol>' : '</ul>';
        }

        return html;
    }

    function initAdminMarkdownFields() {
        const iaField = document.getElementById('id_descricao_ia');
        if (!iaField || iaField.dataset.mdEnhanced === 'true') return;

        iaField.dataset.mdEnhanced = 'true';

        // Cria o container do card formatado
        const wrapper = document.createElement('div');
        wrapper.className = 'admin-md-card-wrapper';
        wrapper.id = 'admin-md-wrapper-id_descricao_ia';

        wrapper.innerHTML = `
            <div class="admin-md-toolbar">
                <div class="admin-md-tabs">
                    <button type="button" class="admin-md-tab-btn is-active" data-mode="rendered" title="Visualizar descrição formatada em tela cheia">
                        <svg viewBox="0 0 24 24" style="width:13px; height:13px; stroke:currentColor; fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round;"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                        <span>Visual Formatado</span>
                    </button>
                    <button type="button" class="admin-md-tab-btn" data-mode="split" title="Editar Markdown à direita e acompanhar a formatação ao vivo à esquerda">
                        <svg viewBox="0 0 24 24" style="width:13px; height:13px; stroke:currentColor; fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round;"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M12 3v18"/><path d="m16 8 2 2-2 2"/><path d="m8 14-2-2 2-2"/></svg>
                        <span>Código / Markdown</span>
                    </button>
                </div>
                <div class="admin-md-toolbar-actions">
                    <span class="admin-md-live-badge" id="admin-md-live-indicator" style="display: none;" title="Edições no Markdown são atualizadas instantaneamente na prévia">
                        <span class="admin-md-live-dot"></span> Ao Vivo
                    </span>
                    <button type="button" class="admin-md-copy-btn" id="btn-copy-ia-to-manual" title="Copiar este texto da IA para o campo 'Descrição Manual / Final' para poder personalizá-lo">
                        <svg viewBox="0 0 24 24" style="width:13px; height:13px; stroke:currentColor; fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round;"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>
                        <span>Copiar para Descrição Manual</span>
                    </button>
                </div>
            </div>
            <div class="admin-md-workspace mode-rendered" id="admin-md-workspace-id_descricao_ia">
                <!-- Painel Esquerdo: Prévia Formatada -->
                <div class="admin-md-pane admin-md-preview-pane">
                    <div class="admin-md-pane-header">
                        <div class="admin-md-pane-title">
                            <svg viewBox="0 0 24 24" style="width:12px; height:12px; stroke:currentColor; fill:none; stroke-width:1.8;"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                            <span>Prévia Visual (Ao Vivo)</span>
                        </div>
                        <span class="admin-md-pane-badge">Renderização em Tempo Real</span>
                    </div>
                    <div class="admin-md-rendered-view" id="admin-md-rendered-id_descricao_ia"></div>
                </div>

                <!-- Painel Direito: Editor Markdown -->
                <div class="admin-md-pane admin-md-editor-pane">
                    <div class="admin-md-pane-header">
                        <div class="admin-md-pane-title">
                            <svg viewBox="0 0 24 24" style="width:12px; height:12px; stroke:currentColor; fill:none; stroke-width:1.8;"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                            <span>Código Markdown (Editor)</span>
                        </div>
                        <span class="admin-md-stats" id="admin-md-stats-id_descricao_ia">0 caracteres</span>
                    </div>
                    <div class="admin-md-editor-body" id="admin-md-editor-slot-id_descricao_ia"></div>
                </div>
            </div>
        `;

        // Insere o card antes da textarea
        iaField.parentNode.insertBefore(wrapper, iaField);

        // Move a textarea nativa para o slot do editor (preservando o formulário Django)
        const editorSlot = wrapper.querySelector('#admin-md-editor-slot-id_descricao_ia');
        editorSlot.appendChild(iaField);

        const workspace = wrapper.querySelector('#admin-md-workspace-id_descricao_ia');
        const renderedView = wrapper.querySelector('#admin-md-rendered-id_descricao_ia');
        const tabBtns = wrapper.querySelectorAll('.admin-md-tab-btn');
        const liveIndicator = wrapper.querySelector('#admin-md-live-indicator');
        const statsEl = wrapper.querySelector('#admin-md-stats-id_descricao_ia');
        const copyBtn = wrapper.querySelector('#btn-copy-ia-to-manual');

        const updateStats = () => {
            if (!statsEl) return;
            const text = iaField.value || '';
            const charCount = text.length;
            const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
            statsEl.textContent = `${charCount} caracteres • ${wordCount} palavras`;
        };

        const updateRendered = () => {
            renderedView.innerHTML = parseMarkdownToHtml(iaField.value);
            updateStats();
        };

        // Renderiza estado inicial
        updateRendered();

        // Escuta digitação em tempo real na textarea (modo split/edição)
        iaField.addEventListener('input', updateRendered);
        iaField.addEventListener('keyup', updateRendered);
        iaField.addEventListener('paste', () => setTimeout(updateRendered, 50));
        iaField.addEventListener('change', updateRendered);

        // Alternância de abas
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                tabBtns.forEach(b => b.classList.remove('is-active'));
                btn.classList.add('is-active');

                const mode = btn.dataset.mode;
                if (mode === 'rendered') {
                    workspace.className = 'admin-md-workspace mode-rendered';
                    if (liveIndicator) liveIndicator.style.display = 'none';
                    updateRendered();
                } else {
                    workspace.className = 'admin-md-workspace mode-split';
                    if (liveIndicator) liveIndicator.style.display = 'inline-flex';
                    updateRendered();
                    iaField.focus();
                }
            });
        });

        // Ação de copiar para Descrição Manual
        if (copyBtn) {
            copyBtn.addEventListener('click', (e) => {
                e.preventDefault();
                const manualField = document.getElementById('id_descricao_manual');
                if (!manualField) {
                    showAdminSubtleToast('Campo de Descrição Manual não encontrado.', true);
                    return;
                }

                if (!iaField.value.trim()) {
                    showAdminSubtleToast('Descrição de IA está vazia no momento.', true);
                    return;
                }

                manualField.value = iaField.value;
                manualField.dispatchEvent(new Event('input', { bubbles: true }));
                manualField.dispatchEvent(new Event('change', { bubbles: true }));

                showAdminSubtleToast('✓ Descrição copiada para o campo Descrição Manual!');
                manualField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                manualField.focus();
            });
        }
    }

    function updateAdminMarkdownPreviews() {
        const iaField = document.getElementById('id_descricao_ia');
        const renderedView = document.getElementById('admin-md-rendered-id_descricao_ia');
        const statsEl = document.getElementById('admin-md-stats-id_descricao_ia');
        if (iaField && renderedView) {
            renderedView.innerHTML = parseMarkdownToHtml(iaField.value);
            if (statsEl) {
                const text = iaField.value || '';
                const charCount = text.length;
                const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
                statsEl.textContent = `${charCount} caracteres • ${wordCount} palavras`;
            }
        }
    }

    async function loadSerpApiQuota() {
        const badges = document.querySelectorAll('.serpapi-quota-badge, #serpapi-quota-badge');
        if (badges.length === 0) return;

        try {
            const resp = await fetch('/ai/serpapi-quota/');
            if (resp.ok) {
                const data = await resp.json();
                const text = data.formatted || (data.available ? `${data.searches_left}/${data.searches_total} rest.` : '');
                badges.forEach(b => {
                    if (text) {
                        b.textContent = text;
                        b.style.display = 'inline-block';
                        b.setAttribute('title', `Cota SerpApi: ${data.searches_left} restantes de ${data.searches_total} este mês (Usadas: ${data.this_month_usage})`);
                    } else {
                        b.style.display = 'none';
                    }
                });
            }
        } catch (e) {
            console.debug('Não foi possível carregar cota SerpApi:', e);
        }
    }

    // Inicialização ao carregar o DOM
    document.addEventListener('DOMContentLoaded', () => {
        initAdminMarkdownFields();
    });

    window.updateAdminMarkdownPreviews = updateAdminMarkdownPreviews;
    window.loadSerpApiQuota = loadSerpApiQuota;
})();

