"""Serializers for registers app - SZCO/individual entities and related data."""
from rest_framework import serializers
from .models import IndividualEntity


class IndividualEntityListSerializer(serializers.ModelSerializer):
    """Minimal serializer for IndividualEntity list view - quick search/browse."""

    debt_status = serializers.SerializerMethodField()
    vat_status = serializers.SerializerMethodField()

    class Meta:
        model = IndividualEntity
        fields = [
            'id', 'ico', 'nazov_UJ', 'pravna_forma', 'mesto',
            'debt_status', 'vat_status', 'datum_poslednej_upravy'
        ]

    def get_debt_status(self, obj):
        """Combine VSZP and social insurance debts."""
        total = (obj.debt_vszp or 0) + (obj.debt_soc_poist or 0)
        return {
            'has_debt': total > 0,
            'total_amount': total,
            'vszp': float(obj.debt_vszp) if obj.debt_vszp else None,
            'social_insurance': float(obj.debt_soc_poist) if obj.debt_soc_poist else None,
            'last_checked': obj.last_insurance_debt.isoformat() if obj.last_insurance_debt else None
        }

    def get_vat_status(self, obj):
        """Show VAT payer status and tax debt."""
        return {
            'is_payer': obj.vat_payer,
            'ic_dph': obj.ic_dph,
            'registered_date': obj.datum_reg_dph.isoformat() if obj.datum_reg_dph else None,
            'deleted_date': obj.vat_deleted_date.isoformat() if obj.vat_deleted_date else None,
            'tax_debt': float(obj.tax_debt) if obj.tax_debt else None,
        }


class IndividualEntityDetailSerializer(serializers.ModelSerializer):
    """Complete serializer for IndividualEntity detail view."""

    debt_details = serializers.SerializerMethodField()
    tax_details = serializers.SerializerMethodField()

    class Meta:
        model = IndividualEntity
        fields = [
            # Basic info
            'id', 'ruz_id', 'ico', 'dic', 'sid', 'nazov_UJ',
            # Address
            'ulica', 'mesto', 'psc', 'kraj', 'okres', 'sidlo',
            # Business info
            'pravna_forma', 'sk_NACE', 'velkost_organizacie', 'druh_vlastnictva',
            'datum_zalozenia', 'datum_zrusenia',
            # Financial data
            'id_uctovnych_zavierok', 'id_vyrocnych_sprav',
            'uses_ifrs', 'konsolidovana',
            # Debt & tax info
            'debt_details', 'tax_details',
            # Metadata
            'zdroj_dat', 'datum_poslednej_upravy'
        ]
        read_only_fields = fields

    def get_debt_details(self, obj):
        """Detailed debt information."""
        return {
            'vszp': {
                'amount': float(obj.debt_vszp) if obj.debt_vszp else None,
                'checked_at': obj.last_insurance_debt.isoformat() if obj.last_insurance_debt else None
            },
            'social_insurance': {
                'amount': float(obj.debt_soc_poist) if obj.debt_soc_poist else None,
                'checked_at': obj.last_insurance_debt.isoformat() if obj.last_insurance_debt else None
            },
            'total': float((obj.debt_vszp or 0) + (obj.debt_soc_poist or 0))
        }

    def get_tax_details(self, obj):
        """Detailed tax information from Financial Authority (FS)."""
        return {
            'vat_payer': obj.vat_payer,
            'vat_id': obj.ic_dph,
            'registered_at': obj.datum_reg_dph.isoformat() if obj.datum_reg_dph else None,
            'deleted_at': obj.vat_deleted_date.isoformat() if obj.vat_deleted_date else None,
            'deleted_reason': obj.vat_deleted_reason,
            'tax_debt': float(obj.tax_debt) if obj.tax_debt else None,
            'reliability_index': obj.tax_reliability,
            'bank_accounts': obj.bank_accounts or [],
            'last_updated': obj.fs_update_date.isoformat() if obj.fs_update_date else None
        }

