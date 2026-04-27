"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from pathlib import Path
from app.views import home, login_view, logout_view, info, wybierz_pacjenta, dodaj_pacjenta, aktualizuj_pacjenta, test, zapisz_wyniki, badanie_zapisz, badanie_wynik, get_pacjent_data, export_wyniki

BASE_DIR = Path(__file__).resolve().parent.parent

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('info/', info, name='info'),
    path('info/wybierz_pacjenta/', wybierz_pacjenta, name='wybierz_pacjenta'),
    path('info/get_pacjent_data/<int:pacjent_id>/', get_pacjent_data, name='get_pacjent_data'),
    path('info/dodaj_pacjenta/', dodaj_pacjenta, name='dodaj_pacjenta'),
    path('info/aktualizuj_pacjenta/', aktualizuj_pacjenta, name='aktualizuj_pacjenta'),
    path('info/test/', test, name='test'),
    path('info/test/zapisz/', zapisz_wyniki, name='zapisz_wyniki'),
    path('info/export/', export_wyniki, name='export_wyniki'),
    path('badanie/zapisz/', badanie_zapisz, name='badanie_zapisz'),
    path('badanie/wynik/', badanie_wynik, name='badanie_wynik'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=str(BASE_DIR / 'app' / 'templates'))
