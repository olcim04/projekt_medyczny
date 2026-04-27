import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

# Tworzenie przykładowych użytkowników
users_data = [
    {'username': 'admin', 'password': 'admin123', 'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True},
    {'username': 'anna', 'password': 'anna123', 'email': 'anna@example.com', 'is_staff': False, 'is_superuser': False},
    {'username': 'piotr', 'password': 'piotr123', 'email': 'piotr@example.com', 'is_staff': False, 'is_superuser': False},
]

print("Tworzenie użytkowników...")
for user_data in users_data:
    if not User.objects.filter(username=user_data['username']).exists():
        user = User.objects.create_user(
            username=user_data['username'],
            password=user_data['password'],
            email=user_data['email'],
            is_staff=user_data['is_staff'],
            is_superuser=user_data['is_superuser'],
            first_name=user_data['username'].capitalize()
        )
        print(f"✓ Utworzony: {user_data['username']} (hasło: {user_data['password']})")
    else:
        print(f"⚠ Już istnieje: {user_data['username']}")

print("\n=== DANE DO LOGOWANIA ===")
users = User.objects.all()
for u in users:
    print(f"\nUsername: {u.username}")
    role = "Administrator" if u.is_superuser else "Użytkownik"
    print(f"Rola: {role}")
    print(f"Email: {u.email}")
