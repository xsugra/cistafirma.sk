from django.core.management.base import BaseCommand
from companies.models import Company
from registers.models import OrsrCompanyProfile
from datetime import date


class Command(BaseCommand):
    help = 'Create ORSR profile for test company 50059959'

    def handle(self, *args, **options):
        # Create or get company
        company, created = Company.objects.get_or_create(
            ico='50059959',
            defaults={
                'ruz_id': 999999,
                'nazov_UJ': 'Quantum Solutions s. r. o.',
                'mesto': 'Bratislava',
                'ulica': 'Mlynské nivy 42',
                'psc': '821 09',
                'pravna_forma': '112',
                'datum_zalozenia': date(2015, 10, 21),
            }
        )

        self.stdout.write(f"Company: {'Created' if created else 'Existing'} - {company.nazov_UJ}")

        # Create or update ORSR profile
        profile, profile_created = OrsrCompanyProfile.objects.update_or_create(
            company=company,
            defaults={
                'ico': '50059959',
                'oddiel': 'Sr',
                'vlozka_cislo': '123/S',
                'obchodne_meno': 'Quantum Solutions s. r. o.',
                'sidlo': 'Mlynské nivy 42, 821 09 Bratislava',
                'den_zapisu': date(2015, 10, 21),
                'pravna_forma': 'Spoločnosť s ručením obmedzeným',
                'vyska_zakladneho_imania': '100 000 EUR',
                'predmet_podnikania': [
                    'Poskytovanie služieb v oblasti IT',
                    'Vývoj softvérových aplikácií',
                    'Poradenstvo v oblasti informačných technológií',
                    'Predaj a servisy počítačovej techniky',
                    'Predaj počítačového softvéru',
                ],
                'spolocnici': [
                    'Ján Vážny - 50%',
                    'Future Investments, s.r.o. - 50%',
                ],
                'vklady_spolocnikov': [
                    'Ján Vážny: 50 000 EUR',
                    'Future Investments, s.r.o.: 50 000 EUR',
                ],
                'statutarny_organ': [
                    'Ing. Ján Vážny',
                    'Mgr. Eva Múdra',
                ],
                'prokura': [
                    'Ing. Peter Procházka',
                ],
                'orsr_aktualizacia_dat': date(2024, 7, 15),
                'orsr_datum_vypisu': date(2024, 7, 20),
                'fetch_ok': True,
            }
        )

        self.stdout.write(self.style.SUCCESS(f"ORSR Profile: {'Created' if profile_created else 'Updated'}"))
        self.stdout.write(f"  Spoločníci: {len(profile.spolocnici)}")
        self.stdout.write(f"  Štatutárny orgán: {len(profile.statutarny_organ)}")
        self.stdout.write(f"  Prokúra: {len(profile.prokura)}")
        self.stdout.write(f"  Predmety podnikania: {len(profile.predmet_podnikania)}")

