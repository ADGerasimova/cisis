"""
API эндпоинты (JSON responses)
"""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from core.models import Contract


@login_required
def get_client_contracts(request, client_id):
    """
    API: Получить список договоров клиента (для AJAX)
    """
    contracts = Contract.objects.filter(
        client_id=client_id,
        status='ACTIVE'
    ).values('id', 'number', 'date')

    return JsonResponse({
        'contracts': list(contracts)
    })