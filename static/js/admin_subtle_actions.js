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

    async function handleLensClick(btn) {
        const relativeUrl = btn.getAttribute('data-image-url');
        if (!relativeUrl) return;

        // Monta a URL pública absoluta
        const fullUrl = window.location.origin + relativeUrl;
        const lensUrl = `https://lens.google.com/uploadbyurl?url=${encodeURIComponent(fullUrl)}`;

        // Tenta copiar a imagem ou a URL para a área de transferência
        let copied = false;
        try {
            if (navigator.clipboard && window.fetch) {
                const imgResp = await fetch(relativeUrl);
                const blob = await imgResp.blob();
                // Converte para PNG garantido se suportado
                if (window.ClipboardItem) {
                    const pngBlob = blob.type === 'image/png' ? blob : new Blob([blob], { type: 'image/png' });
                    await navigator.clipboard.write([
                        new ClipboardItem({ 'image/png': pngBlob })
                    ]);
                    copied = true;
                } else {
                    await navigator.clipboard.writeText(fullUrl);
                    copied = true;
                }
            }
        } catch (e) {
            try {
                if (navigator.clipboard) {
                    await navigator.clipboard.writeText(fullUrl);
                    copied = true;
                }
            } catch (_) {}
        }

        // Abre o Google Lens com a URL da imagem carregada
        window.open(lensUrl, '_blank', 'noopener,noreferrer');

        const msg = copied 
            ? '🔍 Abrindo Google Lens com a foto! (Imagem copiada para a área de transferência)'
            : '🔍 Abrindo Google Lens com a imagem...';
        showAdminSubtleToast(msg, false, '🔍');
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

    function showAdminSubtleToast(message, isError = false, customIcon = '') {
        let container = document.getElementById('admin-subtle-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'admin-subtle-toast-container';
            document.body.appendChild(container);
        }

        const icon = isError ? '⚠️' : (customIcon || '✅');
        const toast = document.createElement('div');
        toast.className = `admin-subtle-toast ${isError ? 'toast-error' : ''}`;
        toast.innerHTML = `
            <span>${icon}</span>
            <span>${message}</span>
        `;

        container.appendChild(toast);

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

    window.loadSerpApiQuota = loadSerpApiQuota;
})();
