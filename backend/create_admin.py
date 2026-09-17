#!/usr/bin/env python
"""Create Django admin account."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Skontroluj či user existuje
if User.objects.filter(username='admin').exists():
    u = User.objects.get(username='admin')
    u.set_password('admin')
    u.save()
    print("✓ Admin account už existoval, heslo aktualizované")
else:
    # Vytvor nový superuser
    u = User.objects.create_superuser(username='admin', email='admin@localhost', password='admin')
    print("✓ Nový admin account vytvorený")

print("\n✅ ADMIN ACCOUNT READY:")
print("   Username: admin")
print("   Password: admin")
print("   URL: http://localhost:8000/admin/")
print("   Alebo: http://localhost:8080/admin/ (external port)")

