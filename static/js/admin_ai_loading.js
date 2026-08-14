/**
 * Django Admin AI Action Loading Overlay - Hub de Desapego
 * Exibe animação ao disparar processamentos de IA no painel administrativo do Django.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Intercepta cliques em botões ou links que chamam a IA no admin
    document.addEventListener('click', (e) => {
        const aiLink = e.target.closest('a[href*="/ai/process/"], a[title*="orquestrador de IA"], a[title*="Executar orquestrador"]');
        if (aiLink) {
            showAdminLoadingOverlay("Executando pipeline de Inteligência Artificial...", "Analisando visão computacional, preços e copywriting...");
        }
    });

    // Intercepta submissão do formulário de ações em lote
    const changelistForm = document.getElementById('changelist-form');
    if (changelistForm) {
        changelistForm.addEventListener('submit', (e) => {
            const actionSelect = changelistForm.querySelector('select[name="action"]');
            if (actionSelect && actionSelect.value === 'processar_com_ia') {
                showAdminLoadingOverlay("Processando itens selecionados com IA...", "Aguarde enquanto as imagens e preços de cada item são processados.");
            }
        });
    }
});

function showAdminLoadingOverlay(title, subtitle) {
    if (document.getElementById('admin-ai-loading-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'admin-ai-loading-overlay';
    overlay.style.position = 'fixed';
    overlay.style.inset = '0';
    overlay.style.backgroundColor = 'rgba(15, 23, 42, 0.75)';
    overlay.style.backdropFilter = 'blur(6px)';
    overlay.style.zIndex = '999999';
    overlay.style.display = 'flex';
    overlay.style.alignItems = 'center';
    overlay.style.justifyContent = 'center';
    overlay.style.padding = '1rem';
    overlay.style.fontFamily = 'system-ui, -apple-system, sans-serif';

    overlay.innerHTML = `
        <div style="background: #ffffff; padding: 2rem; border-radius: 1.25rem; max-width: 420px; width: 100%; text-align: center; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.04); border: 1px solid #e2e8f0;">
            <div style="width: 50px; height: 50px; border: 4px solid #9333ea; border-top-color: transparent; border-radius: 50%; animation: admin-spin 0.8s linear infinite; margin: 0 auto 1.25rem;"></div>
            <h3 style="margin: 0 0 0.5rem 0; font-size: 1.125rem; font-weight: 800; color: #0f172a;">${title}</h3>
            <p style="margin: 0; font-size: 0.875rem; color: #64748b; line-height: 1.4;">${subtitle}</p>
        </div>
        <style>
            @keyframes admin-spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    `;

    document.body.appendChild(overlay);
}
