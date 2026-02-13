from django import forms
from .models import (
    FactoryComplianceDocument,
    PolicyComplianceDocument,
    ProductComplianceDocument,
    SopsComplianceDocument,
    SpecSheet,
    ReportSheet,
)

DATE_INPUTS = ["%d-%m-%Y", "%Y-%m-%d"]  # dd-mm-yyyy + ISO fallback


class BaseComplianceForm(forms.ModelForm):
    issue_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )
    expiry_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUTS,
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )

    class Meta:
        fields = "__all__"


class FactoryComplianceForm(BaseComplianceForm):
    class Meta(BaseComplianceForm.Meta):
        model = FactoryComplianceDocument


class PolicyComplianceForm(BaseComplianceForm):
    class Meta(BaseComplianceForm.Meta):
        model = PolicyComplianceDocument


class ProductComplianceForm(BaseComplianceForm):
    class Meta(BaseComplianceForm.Meta):
        model = ProductComplianceDocument


class SopsComplianceForm(BaseComplianceForm):
    class Meta(BaseComplianceForm.Meta):
        model = SopsComplianceDocument


class SpecSheetForm(BaseComplianceForm):
    class Meta(BaseComplianceForm.Meta):
        model = SpecSheet


class ReportSheetForm(BaseComplianceForm):
    class Meta(BaseComplianceForm.Meta):
        model = ReportSheet

