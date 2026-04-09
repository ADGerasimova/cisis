import os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.conf import settings
from django.templatetags.static import static

from core.services.workspace_menu import get_available_journals
from core.services.metrology_checker import maybe_check_metrology
from core.services.maintenance_checker import maybe_check_maintenance

def _get_meme_urls():
    memes_dir = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'stickers', 'mem')
    if not os.path.isdir(memes_dir): return []
    return [static(f'core/stickers/mem/{f}') for f in sorted(os.listdir(memes_dir)) if f.lower().endswith(('.png','.jpg','.jpeg','.gif','.webp'))]

@login_required
def workspace_home(request):
    user = request.user
    maybe_check_metrology()
    maybe_check_maintenance()
    
    return render(request, 'core/workspace_home.html', {
        'journals': get_available_journals(user), # <-- теперь одна строка
        'user': user,
        'meme_urls': _get_meme_urls(),
    })

@login_required
def logout_view(request):
    logout(request)
    return redirect('/workspace')