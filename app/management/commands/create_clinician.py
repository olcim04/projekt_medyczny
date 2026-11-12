from getpass import getpass

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.models import Uzytkownik


class Command(BaseCommand):
    help = 'Create a clinician login and explicitly link it to a UZYTKOWNIK profile.'

    def add_arguments(self, parser):
        parser.add_argument('--username')
        parser.add_argument('--first-name')
        parser.add_argument('--last-name')
        parser.add_argument('--email', default='')
        parser.add_argument('--profile-id', type=int)
        parser.add_argument('--specialista', default='klinicysta')

    def handle(self, *args, **options):
        if options['specialista'] not in {'klinicysta', 'admin'}:
            raise CommandError('specialista musi mieć wartość "klinicysta" lub "admin".')

        username = (options['username'] or input('Login: ')).strip()
        if not username:
            raise CommandError('Login nie może być pusty.')

        user = User.objects.filter(username=username).first()
        if user is None:
            first_name = (options['first_name'] or input('Imię: ')).strip()
            last_name = (options['last_name'] or input('Nazwisko: ')).strip()
            email = options['email'].strip() or input('E-mail (opcjonalnie): ').strip()
            password = getpass('Hasło: ')
            if password != getpass('Powtórz hasło: '):
                raise CommandError('Podane hasła nie są takie same.')
            if not password:
                raise CommandError('Hasło nie może być puste.')

            user = User(username=username, first_name=first_name, last_name=last_name, email=email)
            validate_password(password, user)
        else:
            first_name = (options['first_name'] or user.first_name).strip()
            last_name = (options['last_name'] or user.last_name).strip()
            email = user.email
            password = None

        profile = (
            Uzytkownik.objects.filter(auth_user_id=user.pk).first()
            if user.pk is not None
            else None
        )
        profile_id = options['profile_id']
        if profile is not None and profile_id is not None and profile.pk != profile_id:
            raise CommandError('To konto jest już powiązane z innym profilem klinicznym.')

        if profile is None and profile_id is None:
            unlinked = Uzytkownik.objects.filter(auth_user__isnull=True).order_by('id_uzytkownika')
            for candidate in unlinked:
                self.stdout.write(
                    f'{candidate.id_uzytkownika}: {candidate.imie} {candidate.nazwisko} '
                    f'({candidate.specjalista})'
                )
            selected = input(
                'ID istniejącego, niepowiązanego profilu (Enter utworzy nowy): '
            ).strip()
            profile_id = int(selected) if selected else None

        with transaction.atomic():
            if user.pk is None:
                user.set_password(password)
                user.save()

            if profile_id is not None:
                try:
                    profile = Uzytkownik.objects.select_for_update().get(pk=profile_id)
                except Uzytkownik.DoesNotExist as error:
                    raise CommandError(f'Nie znaleziono profilu UZYTKOWNIK o ID {profile_id}.') from error
                if profile.auth_user_id not in (None, user.pk):
                    raise CommandError('Wybrany profil jest już powiązany z innym kontem.')
                if profile.auth_user_id is None:
                    profile.auth_user = user
                    profile.save(update_fields=['auth_user'])
            elif profile is None:
                if not first_name or not last_name:
                    raise CommandError(
                        'Aby utworzyć nowy profil, podaj imię i nazwisko.'
                    )
                profile = Uzytkownik.objects.create(
                    imie=first_name,
                    nazwisko=last_name,
                    specjalista=options['specialista'],
                    auth_user=user,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Utworzono/potwierdzono konto "{user.username}" i powiązano '
                f'je z profilem UZYTKOWNIK ID {profile.pk}.'
            )
        )
