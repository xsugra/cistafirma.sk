from rest_framework import serializers
from .models import Company
import re
from django.core.exceptions import ObjectDoesNotExist


PERSON_SKIP_PREFIXES = (
    'vklad:',
    'splatené:',
    'vznik funkcie:',
    'spôsob konania',
    'konatelia',
    'prokúra',
    'prokurista',
)

class CompanyListSerializer(serializers.ModelSerializer):
    legal_form_short = serializers.CharField(source='get_legal_form_short', read_only=True)
    
    class Meta:
        model = Company
        fields = [
            'id', 'ico', 'ruz_id', 'nazov_UJ', 'mesto', 'ulica', 'psc', 
            'pravna_forma', 'legal_form_short', 'datum_zalozenia', 
            'tax_debt', 'debt_vszp', 'debt_soc_poist'
        ]

class CompanyDetailSerializer(serializers.ModelSerializer):
    legal_form = serializers.CharField(source='get_legal_form_display', read_only=True)
    financials = serializers.SerializerMethodField()
    executives = serializers.SerializerMethodField()
    connections = serializers.SerializerMethodField()
    orsr_profile = serializers.SerializerMethodField()

    # Mapovanie na frontend format ak je to nutne, ale skusime poslat co najviac dat
    class Meta:
        model = Company
        fields = '__all__'

    def get_financials(self, obj):
        results = obj.financial_results.all().order_by('year')
        return [
            {
                'year': result.year,
                'revenue': float(result.revenue or 0),
                'profit': float(result.profit or 0),
            }
            for result in results
        ]

    def _get_orsr_profile(self, obj):
        try:
            return obj.orsr_profile
        except ObjectDoesNotExist:
            return None

    def get_executives(self, obj):
        profile = self._get_orsr_profile(obj)
        if not profile:
            return []

        executives = []
        for name in self._extract_person_names(profile.statutarny_organ):
            executives.append({'name': name, 'role': 'Konateľ'})

        for name in self._extract_person_names(getattr(profile, 'prokura', [])):
            executives.append({'name': name, 'role': 'Prokurista'})

        existing_names = {entry['name'] for entry in executives}
        for name in self._extract_person_names(profile.spolocnici):
            if name in existing_names:
                continue
            executives.append({'name': name, 'role': 'Spoločník'})

        return executives

    def get_connections(self, obj):
        # Aktuálne prepojenia vraciame ako ORSR osoby naviazané na firmu.
        # Neskôr je možné rozšíriť o cross-company graf medzi firmami.
        executives = self.get_executives(obj)
        status = 'Vymazaná' if obj.datum_zrusenia else 'Aktívna'
        return [
            {
                'companyName': person['name'],
                'ico': obj.ico,
                'role': person['role'],
                'status': status,
            }
            for person in executives
        ]

    def get_orsr_profile(self, obj):
        profile = self._get_orsr_profile(obj)
        if not profile:
            return None

        # Detekuj typ ORSR (Sr, Sro, Dr, atď.)
        oddiel_type = self._detect_oddiel_type(profile.oddiel)
        
        result = {
            'oddiel': profile.oddiel,
            'oddiel_type': oddiel_type or profile.oddiel_type,
            'vlozka_cislo': profile.vlozka_cislo,
            'obchodne_meno': profile.obchodne_meno,
            'sidlo': profile.sidlo,
            'den_zapisu': profile.den_zapisu,
            'pravna_forma': profile.pravna_forma,
            'konanie': profile.konanie,
            'prokura': profile.prokura,
            'spolocnici': profile.spolocnici,
            'statutarny_organ': profile.statutarny_organ,
            'vklady_spolocnikov': profile.vklady_spolocnikov,
            'vyska_zakladneho_imania': profile.vyska_zakladneho_imania,
            'predmet_podnikania': profile.predmet_podnikania,
            'raw_sections': profile.raw_sections,
            'orsr_aktualizacia_dat': profile.orsr_aktualizacia_dat,
            'orsr_datum_vypisu': profile.orsr_datum_vypisu,
            'fetch_ok': profile.fetch_ok,
            'last_error': profile.last_error,
        }
        
        # Pridaj polia pre družstvá ak existujú
        if oddiel_type and oddiel_type.lower() == 'dr':
            result.update({
                'predstavenstvo': profile.predstavenstvo,
                'kontrolna_komisia': profile.kontrolna_komisia,
                'zakladny_clensky_vklad': profile.zakladny_clensky_vklad,
                'zapisovane_zakladne_imanie': profile.zapisovane_zakladne_imanie,
                'dalske_pravne_skutocnosti': profile.dalske_pravne_skutocnosti,
            })
        
        return result
    
    def _detect_oddiel_type(self, oddiel_text: str) -> str:
        """Detekuje typ ORSR z textu oddiel (Sr, Sro, Dr, atď.)"""
        if not oddiel_text:
            return ''
        text = oddiel_text.strip().lower()
        for variant in ['sr', 'sro', 'dr', 'vs', 'ks', 'as']:
            if text == variant or text.startswith(variant):
                return variant
        return text.split()[0] if text else ''

    def _extract_person_names(self, raw_items):
        names = []
        for raw in raw_items or []:
            text = (raw or '').strip()
            if not text:
                continue

            # Split multiline records and pick the first line that looks like person name.
            for line in text.split('\n'):
                candidate = line.strip()
                normalized = candidate.lower()
                if not candidate:
                    continue
                if any(normalized.startswith(prefix) for prefix in PERSON_SKIP_PREFIXES):
                    continue
                if re.search(r'\d', candidate):
                    continue
                if len(candidate) < 3:
                    continue
                names.append(candidate)
                break

        deduped = []
        seen = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            deduped.append(name)
        return deduped

