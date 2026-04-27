from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib import messages
from app.models import Badanie, Pacjent, Uzytkownik
from io import BytesIO
import json
import zipfile
from xml.sax.saxutils import escape

def home(request):
    if request.user.is_authenticated:
        return redirect('info')
    return render(request, 'home.html')

def _xlsx_col_letter(index):
    result = ''
    while index >= 0:
        result = chr(ord('A') + (index % 26)) + result
        index = index // 26 - 1
    return result


def _build_xlsx_rows(rows):
    max_cols = max((len(row) for row in rows), default=0)
    widths = []
    for col_index in range(max_cols):
        width = 10
        for row in rows:
            if col_index < len(row):
                value = row[col_index]
                if value is None:
                    continue
                length = len(str(value))
                if length + 2 > width:
                    width = length + 2
        if width > 40:
            width = 40
        widths.append(width)

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
        '<cols>'
    ]

    for idx, width in enumerate(widths, start=1):
        xml_lines.append(f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>')

    xml_lines.extend(['</cols>', '<sheetData>'])

    for row_index, row in enumerate(rows, start=1):
        xml_lines.append(f'<row r="{row_index}">')
        for col_index, value in enumerate(row):
            if value is None or value == '':
                continue
            cell_ref = f'{_xlsx_col_letter(col_index)}{row_index}'
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                xml_lines.append(f'<c r="{cell_ref}" t="n"><v>{value}</v></c>')
            else:
                text = escape(str(value))
                xml_lines.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        xml_lines.append('</row>')

    xml_lines.extend(['</sheetData>', '</worksheet>'])
    return '\n'.join(xml_lines).encode('utf-8')


def _build_xlsx_package(rows, sheet_name='Wyniki'):
    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
    <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>'''.encode('utf-8')

    rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''.encode('utf-8')

    workbook_rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''.encode('utf-8')

    workbook = f'''<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
    <sheets>
        <sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/>
    </sheets>
</workbook>'''.encode('utf-8')

    sheet = _build_xlsx_rows(rows)
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', rels)
        z.writestr('xl/workbook.xml', workbook)
        z.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
        z.writestr('xl/worksheets/sheet1.xml', sheet)
    output.seek(0)
    return output


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        # print('LOGIN_DEBUG', username, password, request.POST.dict())
        if not username or not password:
            messages.error(request, 'Wszystkie pola muszą być wypełnione.')
            return render(request, 'home.html')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            request.session.set_expiry(None)  # wygasa przy zamknięciu przeglądarki
            return redirect('info')
        else:
            messages.error(request, 'Nieprawidłowa nazwa użytkownika lub hasło.')
    return render(request, 'home.html')

@login_required
def info(request):
    # Pobierz użytkownika z tabeli UZYTKOWNIK na podstawie username
    try:
        prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.username)
    except Uzytkownik.DoesNotExist:
        # Spróbuj znaleźć po imieniu z first_name
        try:
            prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.first_name)
        except Uzytkownik.DoesNotExist:
            prowadzacy = None
    
    pacjenci = Pacjent.objects.filter(id_prowadzacego=prowadzacy) if prowadzacy else Pacjent.objects.none()
    wybrany_pacjent_id = request.session.get('wybrany_pacjent')
    wyniki = None
    wybrany_pacjent = None
    if wybrany_pacjent_id:
        try:
            wybrany_pacjent = Pacjent.objects.get(id_pacjenta=wybrany_pacjent_id, id_prowadzacego=prowadzacy)
            wyniki = Badanie.objects.filter(id_pacjenta=wybrany_pacjent).order_by('-data_badania').first()
        except Pacjent.DoesNotExist:
            wybrany_pacjent = None
    return render(request, 'info.html', {
        'pacjenci': pacjenci,
        'wyniki': wyniki,
        'wybrany_pacjent': wybrany_pacjent,
    })

@login_required
def get_pacjent_data(request, pacjent_id):
    try:
        # Pobierz użytkownika z tabeli UZYTKOWNIK
        try:
            prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.username)
        except Uzytkownik.DoesNotExist:
            try:
                prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.first_name)
            except Uzytkownik.DoesNotExist:
                prowadzacy = None
        
        pacjent = Pacjent.objects.get(id_pacjenta=pacjent_id, id_prowadzacego=prowadzacy)
        from datetime import date
        wiek = date.today().year - pacjent.data_urodzenia.year - ((date.today().month, date.today().day) < (pacjent.data_urodzenia.month, pacjent.data_urodzenia.day))
        ostatnie_badanie = Badanie.objects.filter(id_pacjenta=pacjent).order_by('-data_badania', '-id_badania').first()
        plec_map = {'M': 'Mężczyzna', 'K': 'Kobieta', 'Inna': 'Inna'}
        data = {
            'imie': pacjent.imie,
            'nazwisko': pacjent.nazwisko,
            'wiek': wiek,
            'data_urodzenia': str(pacjent.data_urodzenia),
            'plec': pacjent.plec,
            'plec_text': plec_map.get(pacjent.plec, pacjent.plec),
            'nazwa_dokumentu': pacjent.nazwa_dokumentu,
            'numer_dokumentu': pacjent.numer_dokumentu,
            'mial_badanie': ostatnie_badanie is not None,
            'ostatnie_badanie': {
                'wynik_r': ostatnie_badanie.wynik_r if ostatnie_badanie else None,
                'wynik_g': ostatnie_badanie.wynik_g if ostatnie_badanie else None,
                'wynik_b': ostatnie_badanie.wynik_b if ostatnie_badanie else None,
                'wynik_ogolny': ostatnie_badanie.wynik_ogolny if ostatnie_badanie else None,
                'czas_trwania': str(ostatnie_badanie.czas_trwania) if ostatnie_badanie else None,
                'data_badania': str(ostatnie_badanie.data_badania) if ostatnie_badanie else None,
            } if ostatnie_badanie else None
        }
        return JsonResponse(data)
    except Pacjent.DoesNotExist:
        return JsonResponse({'error': 'Pacjent nie znaleziony'}, status=404)

@login_required
def wybierz_pacjenta(request):
    if request.method == 'POST':
        pacjent_id = request.POST.get('pacjent_id')
        if pacjent_id:
            request.session['wybrany_pacjent'] = int(pacjent_id)
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
def dodaj_pacjenta(request):
    if request.method == 'POST':
        imie = (request.POST.get('imie') or '').strip()
        nazwisko = (request.POST.get('nazwisko') or '').strip()
        data_urodzenia = (request.POST.get('data_urodzenia') or '').strip()
        plec = (request.POST.get('plec') or '').strip()
        nazwa_dokumentu = (request.POST.get('nazwa_dokumentu') or '').strip()
        numer_dokumentu = (request.POST.get('numer_dokumentu') or '').strip()

        if not imie or not nazwisko or not data_urodzenia or not plec or not nazwa_dokumentu or not numer_dokumentu:
            messages.error(request, 'Wszystkie pola są wymagane. Wprowadź imię, nazwisko, data urodzenia, płeć i numer dokumentu.')
            return redirect('info')

        if plec not in ['M', 'K', 'Inna']:
            messages.error(request, 'Nieprawidłowa płeć. Wybierz jedną z opcji.')
            return redirect('info')

        from datetime import datetime
        try:
            data_urodzenia = datetime.strptime(data_urodzenia, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Nieprawidłowy format daty urodzenia. Użyj YYYY-MM-DD.')
            return redirect('info')

        # Powiąż aktualny auth_user z tabelą Uzytkownik po imieniu (username)
        try:
            prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.username)
        except Uzytkownik.DoesNotExist:
            # Spróbuj po first_name
            try:
                prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.first_name)
            except Uzytkownik.DoesNotExist:
                # Jeśli nie ma w tabeli Uzytkownik, utwórz tymczasowo
                prowadzacy = Uzytkownik.objects.create(
                    imie=request.user.username,
                    nazwisko=request.user.last_name or '',
                    specjalista='klinicysta'
                )

        Pacjent.objects.create(
            imie=imie,
            nazwisko=nazwisko,
            data_urodzenia=data_urodzenia,
            plec=plec,
            id_prowadzacego=prowadzacy,
            nazwa_dokumentu=nazwa_dokumentu,
            numer_dokumentu=numer_dokumentu
        )

        messages.success(request, 'Pacjent został dodany, a prowadzącym lekarzem jest aktualny użytkownik.')
        return redirect('info')

    return redirect('info')

@login_required
def test(request):
    if not request.session.get('wybrany_pacjent'):
        messages.error(request, 'Najpierw wybierz pacjenta')
        return redirect('info')
    return render(request, 'test.html')

@login_required
def aktualizuj_pacjenta(request):
    if request.method == 'POST':
        pacjent_id = (request.POST.get('pacjent_id') or '').strip()
        imie = (request.POST.get('imie') or '').strip()
        nazwisko = (request.POST.get('nazwisko') or '').strip()
        data_urodzenia = (request.POST.get('data_urodzenia') or '').strip()
        plec = (request.POST.get('plec') or '').strip()
        nazwa_dokumentu = (request.POST.get('nazwa_dokumentu') or '').strip()
        numer_dokumentu = (request.POST.get('numer_dokumentu') or '').strip()

        if not pacjent_id:
            messages.error(request, 'Brak ID pacjenta. Nie można edytować.')
            return redirect('info')

        if not imie or not nazwisko or not data_urodzenia or not plec or not nazwa_dokumentu or not numer_dokumentu:
            messages.error(request, 'Wszystkie pola są wymagane.')
            return redirect('info')

        if plec not in ['M', 'K', 'Inna']:
            messages.error(request, 'Nieprawidłowa płeć.')
            return redirect('info')

        from datetime import datetime
        try:
            data_urodzenia = datetime.strptime(data_urodzenia, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Nieprawidłowy format daty urodzenia.')
            return redirect('info')

        # Pobierz użytkownika z tabeli UZYTKOWNIK
        try:
            prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.username)
        except Uzytkownik.DoesNotExist:
            try:
                prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.first_name)
            except Uzytkownik.DoesNotExist:
                messages.error(request, 'Nie znaleziono użytkownika w systemie.')
                return redirect('info')

        try:
            pacjent = Pacjent.objects.get(
                id_pacjenta=int(pacjent_id),
                id_prowadzacego=prowadzacy
            )
            pacjent.imie = imie
            pacjent.nazwisko = nazwisko
            pacjent.data_urodzenia = data_urodzenia
            pacjent.plec = plec
            pacjent.nazwa_dokumentu = nazwa_dokumentu
            pacjent.numer_dokumentu = numer_dokumentu
            pacjent.save()
            messages.success(request, 'Dane pacjenta zostały zaktualizowane.')
        except Pacjent.DoesNotExist:
            messages.error(request, 'Pacjent nie znaleziony lub brak uprawnień do edycji.')
        except ValueError:
            messages.error(request, 'Nieprawidłowy ID pacjenta.')

        return redirect('info')

    return redirect('info')

    if not request.session.get('wybrany_pacjent'):
        messages.error(request, 'Najpierw wybierz pacjenta')
        return redirect('info')
    return render(request, 'test.html')


@login_required
def zapisz_wyniki(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        pacjent_id = request.session.get('wybrany_pacjent')
        if not pacjent_id:
            return JsonResponse({'error': 'Brak wybranego pacjenta'}, status=400)
        pacjent = Pacjent.objects.get(id_pacjenta=pacjent_id)
        prowadzacy = Uzytkownik.objects.get(id_uzytkownika=request.user.id)
        Badanie.objects.create(
            id_pacjenta=pacjent,
            id_prowadzacego=prowadzacy,
            data_badania=timezone.now().date(),
            czas_trwania=data['czas'],
            wynik_ogolny=data['wynik_ogolny'],
            wynik_r=data['wynik_r'],
            wynik_g=data['wynik_g'],
            wynik_b=data['wynik_b']
        )
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid method'}, status=405)

@login_required
def export_wyniki(request):
    pacjent_id = request.session.get('wybrany_pacjent')
    if not pacjent_id:
        return JsonResponse({'error': 'Najpierw wybierz pacjenta.'}, status=400)

    # Pobierz użytkownika z tabeli UZYTKOWNIK
    try:
        prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.username)
    except Uzytkownik.DoesNotExist:
        try:
            prowadzacy = Uzytkownik.objects.get(imie__iexact=request.user.first_name)
        except Uzytkownik.DoesNotExist:
            return JsonResponse({'error': 'Nie znaleziono użytkownika w systemie.'}, status=400)

    pacjent = get_object_or_404(Pacjent, id_pacjenta=pacjent_id, id_prowadzacego=prowadzacy)
    test_name = request.GET.get('test_name', '').strip()
    badania = Badanie.objects.filter(id_pacjenta=pacjent).order_by('-data_badania')
    if not badania.exists():
        return JsonResponse({'error': 'Brak wyników do eksportu dla wybranego pacjenta.'}, status=400)

    rows = []
    rows.append(['Pacjent', f'{pacjent.imie} {pacjent.nazwisko}'])
    if test_name:
        rows.append(['Wybrany test', test_name])
    rows.append([])
    rows.append(['Data badania', 'Czas trwania', 'Wynik ogólny', 'Wynik R', 'Wynik G', 'Wynik B'])

    for badanie in badania:
        rows.append([
            badanie.data_badania.strftime('%Y-%m-%d'),
            str(badanie.czas_trwania),
            float(badanie.wynik_ogolny) if badanie.wynik_ogolny is not None else '',
            float(badanie.wynik_r) if badanie.wynik_r is not None else '',
            float(badanie.wynik_g) if badanie.wynik_g is not None else '',
            float(badanie.wynik_b) if badanie.wynik_b is not None else '',
        ])

    output = _build_xlsx_package(rows, sheet_name='Wyniki')
    filename = f"wyniki_{pacjent.imie}_{pacjent.nazwisko}.xlsx"
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8''{filename}'
    return response

def logout_view(request):
    request.session.flush()
    logout(request)
    messages.info(request, 'Zostałeś wylogowany. Zaloguj się ponownie.')
    return redirect('home')

def badanie_zapisz(request):
    if request.method == 'POST':
        pacjent_id = request.POST.get('pacjent_id') or 1
        prowadzacy_id = request.POST.get('prowadzacy_id') or 1
        czas_trwania = request.POST.get('czas_trwania') or '00:00:00'
        wynik_ogolny = request.POST.get('wynik_ogolny') or 0
        wynik_r = request.POST.get('wynik_r') or 0
        wynik_g = request.POST.get('wynik_g') or 0
        wynik_b = request.POST.get('wynik_b') or 0

        pacjent = Pacjent.objects.filter(pk=pacjent_id).first()
        prowadzacy = Uzytkownik.objects.filter(pk=prowadzacy_id).first()

        if pacjent and prowadzacy:
            Badanie.objects.create(
                id_pacjenta=pacjent,
                id_prowadzacego=prowadzacy,
                id_wykonujacego=prowadzacy,
                data_badania=timezone.now().date(),
                czas_trwania=czas_trwania,
                wynik_ogolny=wynik_ogolny,
                wynik_r=wynik_r,
                wynik_g=wynik_g,
                wynik_b=wynik_b,
            )
            return redirect('badanie_wynik')
        return render(request, 'test.html', {'error': 'Nie znaleziono pacjenta lub prowadzącego'})

    return render(request, 'test.html')


def badanie_wynik(request):
    return render(request, 'info.html', {'message': 'Badanie zapisane w bazie.'})