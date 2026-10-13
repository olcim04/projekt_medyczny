# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models

class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class Badanie(models.Model):
    id_badania = models.AutoField(primary_key=True)
    id_pacjenta = models.ForeignKey('Pacjent', models.DO_NOTHING, db_column='id_pacjenta')
    id_prowadzacego = models.ForeignKey('Uzytkownik', models.DO_NOTHING, db_column='id_prowadzacego')
    id_wykonujacego = models.ForeignKey('Uzytkownik', models.DO_NOTHING, db_column='id_wykonujacego', related_name='badanie_id_wykonujacego_set', blank=True, null=True)
    data_badania = models.DateField()
    czas_trwania = models.TimeField()
    wynik_ogolny = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    wynik_r = models.DecimalField(db_column='wynik_R', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    wynik_g = models.DecimalField(db_column='wynik_G', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    wynik_b = models.DecimalField(db_column='wynik_B', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    wyniki_json = models.TextField(blank=True, null=True)
    test_type = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'BADANIE'


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class Pacjent(models.Model):
    id_pacjenta = models.AutoField(primary_key=True)
    imie = models.CharField(max_length=50)
    nazwisko = models.CharField(max_length=50)
    data_urodzenia = models.DateField()
    plec = models.CharField(max_length=5, choices=[('M', 'Mężczyzna'), ('K', 'Kobieta'), ('Inna', 'Inna')], default='Inna')
    id_prowadzacego = models.ForeignKey('Uzytkownik', models.DO_NOTHING, db_column='id_prowadzacego')
    nazwa_dokumentu = models.CharField(max_length=100, blank=True, null=True)
    numer_dokumentu = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'PACJENT'


class UstawieniaSystemu(models.Model):
    id_ustawienia = models.AutoField(primary_key=True)
    klucz = models.CharField(unique=True, max_length=50)
    wartosc = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'USTAWIENIA_SYSTEMU'


class Uzytkownik(models.Model):
    id_uzytkownika = models.AutoField(primary_key=True)
    imie = models.CharField(max_length=50)
    nazwisko = models.CharField(max_length=50)
    specjalista = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'UZYTKOWNIK'

def badanie_zapisz(request):
    if request.method == "POST":
        pacjent_id = request.POST.get("pacjent_id")
        prowadzacy_id = request.POST.get("prowadzacy_id")
        wynik_ogolny = request.POST.get("wynik_ogolny")
        czas_trwania = request.POST.get("czas_trwania")

        pacjent = Pacjent.objects.get(pk=pacjent_id)
        prowadzacy = Uzytkownik.objects.get(pk=prowadzacy_id)

        Badanie.objects.create(
            id_pacjenta=pacjent,
            id_prowadzacego=prowadzacy,
            data_badania=timezone.now().date(),
            czas_trwania=czas_trwania,
            wynik_ogolny=wynik_ogolny,
            wynik_r=request.POST.get('wynik_r'),
            wynik_g=request.POST.get('wynik_g'),
            wynik_b=request.POST.get('wynik_b'),
        )
        return redirect("badanie_wynik")
    return render(request, "test.html")
