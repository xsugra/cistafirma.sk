# i18n (Internationalization) Implementation for CistaFirma

## Overview

This document describes the i18n setup for the CistaFirma project, focusing on legal form codes and multi-language support using Django's gettext framework.

## Current Implementation

### Legal Forms Dictionary

The legal forms dictionary (`backend/companies/models.py`) has been prepared with gettext markers using `gettext_lazy()`:

```python
from django.utils.translation import gettext_lazy as _

LEGAL_FORMS = {
    '100': _('Physical person - casual activity - registered in tax system'),
    '101': _('Entrepreneur - physical person - not registered in commercial register'),
    # ... more entries
}

LEGAL_FORMS_SHORT = {
    '100': _('Self-employed - casual'),
    '101': _('Entrepreneur'),
    # ... more entries
}
```

The use of `gettext_lazy()` ensures that:
- Strings are marked for translation
- Translations are evaluated lazily (only when needed)
- Django's translation framework can find all marked strings

### Supported Languages

- **English** (base/default) - provided inline in the code
- **Slovak** (sk) - translations can be generated from the base English strings
- **Additional languages** - can be added by following the same process

## Setting Up i18n

### 1. Configure Django Settings

Ensure `backend/backend/settings.py` has i18n enabled:

```python
USE_I18N = True
USE_L10N = True

LANGUAGE_CODE = 'sk'  # Default language: Slovak
LANGUAGES = [
    ('en', 'English'),
    ('sk', 'Slovenčina'),
]

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'companies', 'locale'),
    os.path.join(BASE_DIR, 'backend', 'locale'),
    # Add more apps' locale paths as needed
]
```

### 2. Generate Translation Messages

Extract all marked strings into a message template:

```bash
cd backend
python manage.py makemessages -l en
python manage.py makemessages -l sk
```

This creates:
- `backend/companies/locale/en/LC_MESSAGES/django.po` - English translation file (for context)
- `backend/companies/locale/sk/LC_MESSAGES/django.po` - Slovak translation file (for translation)

### 3. Translate Messages

Edit the `.po` files to add translations:

**File: `backend/companies/locale/sk/LC_MESSAGES/django.po`**

```po
#: companies/models.py:8
msgid "Physical person - casual activity - registered in tax system"
msgstr "Fyzická osoba-príležitostne činná-zapísaná v registri daňového informačného systému"

#: companies/models.py:9
msgid "Entrepreneur - physical person - not registered in commercial register"
msgstr "Podnikateľ-fyzická osoba-nezapísaný v obchodnom registri"

# ... more translations
```

### 4. Compile Translations

After editing `.po` files, compile them into binary `.mo` files:

```bash
cd backend
python manage.py compilemessages
```

This creates:
- `backend/companies/locale/sk/LC_MESSAGES/django.mo` - compiled Slovak translations

### 5. Test Translations

In Django shell or views:

```python
from django.utils.translation import activate, gettext as _
from companies.models import LEGAL_FORMS

# Test English
activate('en')
print(LEGAL_FORMS['112'])  # Output: "Limited liability company"

# Test Slovak
activate('sk')
print(LEGAL_FORMS['112'])  # Output: "Spoločnosť s ručením obmedzeným"
```

## Using Translations in Templates

In Django templates, use the `{% trans %}` tag:

```html
{% load i18n %}

<div>
  <label>{% trans "Legal Form" %}</label>
  <p>{{ company.get_legal_form_display }}</p>
</div>
```

## Using Translations in Views

In Python views/serializers:

```python
from django.utils.translation import activate, gettext_lazy as _

def get_company_form_name(company):
    # Form name will be in the active language
    return company.get_legal_form_display()

# To force a specific language for a code block:
from django.utils.translation import override

with override('en'):
    english_name = company.get_legal_form_display()

with override('sk'):
    slovak_name = company.get_legal_form_display()
```

## Frontend Support (React)

For frontend translations, the API returns localized strings based on the request language or Django's default locale.

If you need client-side translations:

1. **Option A: Language from API**
   - Return translations from the backend API
   - Set HTTP headers: `Accept-Language: sk`

2. **Option B: Client-side i18n (i18next or similar)**
   - Use i18next library in React
   - Implement language files for each language
   - Synchronize with backend translations

Example API response with Accept-Language header:

```python
# In serializer or view
def get_legal_form_display(self, obj):
    return str(obj.get_legal_form_display())  # Returns translated string

# Request: GET /api/companies/12345678/?Accept-Language: sk
# Response: 
{
  "ico": "12345678",
  "nazov_UJ": "Test s. r. o.",
  "pravna_forma": "112",
  "legal_form_display": "Spoločnosť s ručením obmedzeným"
}
```

## Workflow Summary

### For Developers

1. **Add new translatable strings:**
   ```python
   from django.utils.translation import gettext_lazy as _
   
   SOME_TEXT = _('This text will be translated')
   ```

2. **Extract messages:**
   ```bash
   cd backend && python manage.py makemessages -a
   ```

3. **Commit `.po` files** to git (but NOT `.mo` files - they're generated)

4. **Translators edit `.po` files** with appropriate translations

5. **Compile before deployment:**
   ```bash
   cd backend && python manage.py compilemessages
   ```

### For Deployment

The CI/CD pipeline should include:

```bash
# In .gitlab-ci.yml or deployment scripts
cd backend
python manage.py makemessages -a  # Ensure all messages are extracted
python manage.py compilemessages  # Compile before serving
```

## Docker Support

In the Dockerfile, add compilation step:

```dockerfile
# After installing dependencies
RUN cd /app && python manage.py compilemessages
```

## Metrics & Monitoring

The `normalize_legal_form_code()` function includes:
- **Logging**: Unknown codes are logged to `companies.models` logger
- **Prometheus**: Counter `unknown_legal_form_codes_total` with labels `code` and `source`
- **Sentry**: Unknown codes are reported as warnings with tags

Example Prometheus query:
```
increase(unknown_legal_form_codes_total[1d])
```

## Best Practices

1. **Always use `gettext_lazy()`** for module-level strings (dictionaries, defaults)
   - Avoids issues with translation context at import time

2. **Use `gettext()` in functions/methods** that run at request time
   - Ensures current language is respected

3. **Mark plural forms** correctly:
   ```python
   from django.utils.translation import ngettext_lazy
   
   count_msg = ngettext_lazy(
       '%(count)d item',
       '%(count)d items',
       count
   )
   ```

4. **Use context** for ambiguous strings:
   ```python
   from django.utils.translation import pgettext_lazy
   
   action = pgettext_lazy('Legal form context', 'Form')
   ```

5. **Don't translate user input or database values** - only UI strings

6. **Keep translation files small** - consider splitting by domain if project grows

## Troubleshooting

### Translations not appearing

1. Check if `USE_I18N = True` in settings
2. Verify `.mo` file exists: `ls -la backend/companies/locale/sk/LC_MESSAGES/`
3. Run `compilemessages` again
4. Clear Django cache: `python manage.py clear_cache`
5. Check HTTP `Accept-Language` header in requests

### Message extraction incomplete

```bash
# Force full scan
python manage.py makemessages -a --no-wrap --all
```

### Encoding issues

Ensure `.po` files are UTF-8:
```bash
file backend/companies/locale/sk/LC_MESSAGES/django.po
# Should show: UTF-8 Unicode text
```

## Resources

- [Django i18n Documentation](https://docs.djangoproject.com/en/stable/topics/i18n/)
- [gettext Documentation](https://www.gnu.org/software/gettext/manual/)
- [Translator's Guide](https://docs.djangoproject.com/en/stable/topics/i18n/translation/)

