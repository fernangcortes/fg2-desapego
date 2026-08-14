/**
 * Django Admin AI Loading Helper - Hub de Desapego
 * Compatibilidade legada: Redireciona chamadas para o AdminAITerminal sem exibir modal.
 */

window.showAdminLoadingOverlay = function (title, subtitle) {
    if (window.AdminAITerminal) {
        window.AdminAITerminal.open();
        if (title) {
            window.AdminAITerminal.log(`${title} ${subtitle ? '— ' + subtitle : ''}`, { tag: 'INIT' });
        }
    }
};
