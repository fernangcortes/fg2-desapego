/**
 * AI Feedback & Interactive Experience Engine - Hub de Desapego
 * Gerencia animações em tempo real para processamento de IA, uploads e cópia para área de transferência.
 */

const AIFeedback = {
    modalBackdrop: null,
    progressBar: null,
    steps: [],
    currentStep: 0,
    stepInterval: null,
    isProcessing: false,

    init() {
        this.createToastContainer();
        this.createModalStructure();
        this.bindEvents();
    },

    createToastContainer() {
        if (!document.getElementById('toast-container')) {
            const container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
    },

    showToast(message, type = 'success', duration = 3500) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `custom-toast custom-toast-${type}`;

        const icons = {
            success: '✨',
            info: 'ℹ️',
            error: '⚠️'
        };

        toast.innerHTML = `
            <span class="text-base">${icons[type] || '🔔'}</span>
            <span class="flex-1">${message}</span>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('hide');
            setTimeout(() => toast.remove(), 250);
        }, duration);
    },

    createModalStructure() {
        if (document.getElementById('aiProcessingModal')) return;

        const modal = document.createElement('div');
        modal.id = 'aiProcessingModal';
        modal.className = 'ai-modal-backdrop';
        modal.innerHTML = `
            <div class="ai-modal-card" id="aiModalCard">
                <!-- Cabeçalho Animado -->
                <div class="text-center">
                    <div class="ai-orb-container">
                        <div class="ai-ring-2"></div>
                        <div class="ai-ring-1"></div>
                        <div class="ai-orb-core">
                            <span>🧠</span>
                        </div>
                    </div>
                    <h2 class="text-xl font-black text-slate-900 tracking-tight" id="aiModalTitle">
                        Processando com Inteligência Artificial
                    </h2>
                    <p class="text-xs text-slate-500 mt-1" id="aiModalSubtitle">
                        Analisando fotos, pesquisando referências de mercado e otimizando o anúncio...
                    </p>
                </div>

                <!-- Barra de Progresso com listras animadas -->
                <div class="ai-progress-bar-track">
                    <div class="ai-progress-bar-fill animated-stripes" id="aiProgressBar"></div>
                </div>

                <!-- Pipeline de Etapas -->
                <div class="space-y-2.5 my-4" id="aiStepsContainer">
                    <div class="ai-step-item active" id="aiStep0">
                        <div class="ai-step-icon-wrap">1</div>
                        <div class="flex-1 min-w-0">
                            <h4 class="text-xs font-bold text-slate-800">Visão Computacional Multimodal</h4>
                            <p class="text-[11px] text-slate-500">Identificando produto, marca, modelo e detalhes de avarias...</p>
                        </div>
                    </div>

                    <div class="ai-step-item pending" id="aiStep1">
                        <div class="ai-step-icon-wrap">2</div>
                        <div class="flex-1 min-w-0">
                            <h4 class="text-xs font-bold text-slate-800">Pesquisa de Preços de Mercado</h4>
                            <p class="text-[11px] text-slate-500">Consultando cotações em tempo real de novos e usados...</p>
                        </div>
                    </div>

                    <div class="ai-step-item pending" id="aiStep2">
                        <div class="ai-step-icon-wrap">3</div>
                        <div class="flex-1 min-w-0">
                            <h4 class="text-xs font-bold text-slate-800">Copywriting & Precificação Justa</h4>
                            <p class="text-[11px] text-slate-500">Gerando descrição transparente e sugestão ideal de valor...</p>
                        </div>
                    </div>

                    <div class="ai-step-item pending" id="aiStep3">
                        <div class="ai-step-icon-wrap">4</div>
                        <div class="flex-1 min-w-0">
                            <h4 class="text-xs font-bold text-slate-800">Finalização do Desapego</h4>
                            <p class="text-[11px] text-slate-500">Atualizando rascunho e estruturando dados de venda...</p>
                        </div>
                    </div>
                </div>

                <!-- Feedback Dinâmico / Ações Posteriores -->
                <div id="aiModalResultArea" class="hidden text-center pt-2">
                    <!-- Preenchido dinamicamente após conclusão -->
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.modalBackdrop = modal;
        this.progressBar = document.getElementById('aiProgressBar');
    },

    bindEvents() {
        // Escuta botões com o atributo data-ai-process
        document.addEventListener('click', (e) => {
            const aiBtn = e.target.closest('[data-ai-process]');
            if (aiBtn) {
                e.preventDefault();
                const itemId = aiBtn.getAttribute('data-ai-process');
                const redirectTarget = aiBtn.getAttribute('data-ai-redirect') || `/admin/core/item/${itemId}/change/`;
                this.processItem(itemId, { redirectUrl: redirectTarget, triggerBtn: aiBtn });
            }

            // Botões de cópia rápida
            const copyBtn = e.target.closest('[data-copy-target]');
            if (copyBtn) {
                const targetId = copyBtn.getAttribute('data-copy-target');
                const targetEl = document.getElementById(targetId);
                if (targetEl) {
                    const text = targetEl.value !== undefined ? targetEl.value : targetEl.textContent;
                    this.copyTextToClipboard(text, copyBtn);
                }
            }
        });
    },

    processItem(itemId, options = {}) {
        if (this.isProcessing) return;
        this.isProcessing = true;

        const { redirectUrl, triggerBtn, autoRedirect = true, onComplete } = options;

        if (triggerBtn) {
            triggerBtn.classList.add('btn-loading-state');
            triggerBtn.disabled = true;
        }

        this.openModal();
        this.startStepSimulation();

        const endpoint = `/ai/process/${itemId}/?format=json`;

        fetch(endpoint, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(async (response) => {
            const data = await response.json();
            if (!response.ok || data.success === false) {
                throw new Error(data.error || 'Falha ao processar item com IA.');
            }
            return data;
        })
        .then((data) => {
            this.finishSuccess(data, { redirectUrl, autoRedirect, onComplete });
        })
        .catch((error) => {
            this.finishError(error.message, itemId, options);
        })
        .finally(() => {
            this.isProcessing = false;
            if (triggerBtn) {
                triggerBtn.classList.remove('btn-loading-state');
                triggerBtn.disabled = false;
            }
        });
    },

    openModal() {
        this.createModalStructure();
        this.modalBackdrop.classList.add('active');
        this.currentStep = 0;
        this.updateStepUI(0, 15);
        document.getElementById('aiModalResultArea').classList.add('hidden');
        document.getElementById('aiStepsContainer').classList.remove('hidden');
        document.getElementById('aiModalTitle').textContent = 'Processando com Inteligência Artificial';
        document.getElementById('aiModalSubtitle').textContent = 'Analisando fotos, pesquisando referências de mercado e otimizando o anúncio...';
    },

    closeModal() {
        if (this.modalBackdrop) {
            this.modalBackdrop.classList.remove('active');
        }
        clearInterval(this.stepInterval);
    },

    startStepSimulation() {
        clearInterval(this.stepInterval);
        const stepMilestones = [
            { step: 0, progress: 25, delay: 2000 },
            { step: 1, progress: 55, delay: 4500 },
            { step: 2, progress: 85, delay: 7000 },
        ];

        let elapsed = 0;
        const intervalTime = 500;

        this.stepInterval = setInterval(() => {
            elapsed += intervalTime;
            for (let i = stepMilestones.length - 1; i >= 0; i--) {
                if (elapsed >= stepMilestones[i].delay && this.currentStep < stepMilestones[i].step) {
                    this.updateStepUI(stepMilestones[i].step, stepMilestones[i].progress);
                    break;
                }
            }
        }, intervalTime);
    },

    updateStepUI(stepIndex, progressPercent) {
        this.currentStep = stepIndex;
        if (this.progressBar) {
            this.progressBar.style.width = `${progressPercent}%`;
        }

        for (let i = 0; i <= 3; i++) {
            const el = document.getElementById(`aiStep${i}`);
            if (!el) continue;

            const iconWrap = el.querySelector('.ai-step-icon-wrap');
            if (i < stepIndex) {
                el.className = 'ai-step-item completed';
                if (iconWrap) iconWrap.innerHTML = '✓';
            } else if (i === stepIndex) {
                el.className = 'ai-step-item active';
                if (iconWrap) iconWrap.innerHTML = `<span class="btn-spinner"></span>`;
            } else {
                el.className = 'ai-step-item pending';
                if (iconWrap) iconWrap.innerHTML = `${i + 1}`;
            }
        }
    },

    finishSuccess(data, { redirectUrl, autoRedirect, onComplete }) {
        clearInterval(this.stepInterval);
        this.updateStepUI(3, 100);

        // Marca todos como concluídos
        for (let i = 0; i <= 3; i++) {
            const el = document.getElementById(`aiStep${i}`);
            if (el) {
                el.className = 'ai-step-item completed';
                const iconWrap = el.querySelector('.ai-step-icon-wrap');
                if (iconWrap) iconWrap.innerHTML = '✓';
            }
        }

        const resultArea = document.getElementById('aiModalResultArea');
        document.getElementById('aiModalTitle').textContent = '✨ Análise Concluída com Sucesso!';
        document.getElementById('aiModalSubtitle').textContent = 'O anúncio foi gerado, precificado e atualizado.';

        const precoFormatado = data.preco_usado ? `R$ ${parseFloat(data.preco_usado).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : 'Não definido';

        resultArea.innerHTML = `
            <div class="p-3.5 bg-emerald-50 rounded-2xl border border-emerald-200 text-left mb-4 space-y-1.5">
                <span class="text-[10px] font-bold text-emerald-800 uppercase tracking-wider block">Resultado da IA:</span>
                <p class="text-xs font-black text-slate-900 line-clamp-1">${data.titulo || 'Item Atualizado'}</p>
                <div class="flex items-center justify-between text-xs pt-1">
                    <span class="text-slate-600">Preço Sugerido: <strong class="text-emerald-700 font-extrabold">${precoFormatado}</strong></span>
                    <span class="px-2 py-0.5 bg-emerald-100 text-emerald-900 rounded-full font-bold text-[10px] uppercase">${data.categoria || 'Geral'}</span>
                </div>
            </div>

            <div class="flex gap-2">
                ${redirectUrl ? `
                    <a href="${redirectUrl}" class="flex-1 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow transition-all text-center">
                        Continuar para o Item →
                    </a>
                ` : ''}
                <button type="button" onclick="AIFeedback.closeModal()" class="px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-all">
                    Fechar
                </button>
            </div>
        `;

        resultArea.classList.remove('hidden');
        this.showToast('✨ Análise de IA concluída com sucesso!', 'success');

        if (onComplete && typeof onComplete === 'function') {
            onComplete(data);
        }

        if (autoRedirect && redirectUrl) {
            setTimeout(() => {
                window.location.href = redirectUrl;
            }, 1800);
        }
    },

    finishError(errorMessage, itemId, options) {
        clearInterval(this.stepInterval);
        if (this.progressBar) {
            this.progressBar.style.width = '100%';
            this.progressBar.style.background = '#e11d48';
        }

        document.getElementById('aiModalTitle').textContent = '⚠️ Houve um imprevisto';
        document.getElementById('aiModalSubtitle').textContent = 'Não foi possível completar a análise de IA automaticamente.';

        const resultArea = document.getElementById('aiModalResultArea');
        resultArea.innerHTML = `
            <div class="p-3.5 bg-rose-50 rounded-2xl border border-rose-200 text-left mb-4 space-y-1">
                <span class="text-[10px] font-bold text-rose-800 uppercase tracking-wider block">Detalhes do erro:</span>
                <p class="text-xs text-rose-900 font-medium">${errorMessage}</p>
            </div>

            <div class="flex gap-2">
                <button type="button" onclick="AIFeedback.processItem(${itemId}, ${JSON.stringify(options).replace(/"/g, '&quot;')})"
                    class="flex-1 py-3 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs rounded-xl shadow transition-all">
                    🔄 Tentar Novamente
                </button>
                <button type="button" onclick="AIFeedback.closeModal()" class="px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-all">
                    Fechar
                </button>
            </div>
        `;

        resultArea.classList.remove('hidden');
        this.showToast('Erro ao processar item com IA.', 'error');
    },

    copyTextToClipboard(text, buttonElement) {
        if (!navigator.clipboard) {
            // Fallback para navegadores antigos
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        } else {
            navigator.clipboard.writeText(text);
        }

        if (buttonElement) {
            const originalHtml = buttonElement.innerHTML;
            buttonElement.classList.add('btn-copying-success');
            buttonElement.innerHTML = `
                <svg class="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                </svg>
                <span>Copiado!</span>
            `;

            setTimeout(() => {
                buttonElement.classList.remove('btn-copying-success');
                buttonElement.innerHTML = originalHtml;
            }, 2000);
        }

        this.showToast('✓ Texto copiado com sucesso para a área de transferência!', 'success', 2500);
    }
};

// Auto-inicialização quando a página estiver carregada
document.addEventListener('DOMContentLoaded', () => {
    AIFeedback.init();
});
