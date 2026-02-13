# commercial/forms.py
from django import forms
from .models import Warehouse

class WarehouseAdminForm(forms.ModelForm):
    lease_expiry_date = forms.DateField(
        required=False,
        input_formats=["%d-%m-%Y", "%Y-%m-%d"],  # accept Grappelli's value too
        widget=forms.DateInput(
            format="%d-%m-%Y",                  # still display as dd-mm-yyyy
            attrs={"class": "vDateField"},
        ),
    )

    class Meta:
        model = Warehouse
        fields = "__all__"
