from ai_engine.services import SerpApiService

def serpapi_context(request):
    """
    Injeta a cota atual da SerpApi em todas as páginas para usuários staff (Admin).
    """
    if getattr(request, 'user', None) and request.user.is_authenticated and request.user.is_staff:
        return {'serpapi_quota': SerpApiService.get_account_quota()}
    return {'serpapi_quota': {'available': False, 'formatted': ''}}
