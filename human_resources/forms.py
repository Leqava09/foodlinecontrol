from django import forms
from django.forms.widgets import DateInput
from .models import Person, Training, Induction, Leave

DATE_INPUTS = ["%d-%m-%Y", "%Y-%m-%d"]  # dd-mm-yyyy + ISO


class PersonAdminForm(forms.ModelForm):
    hire_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=DateInput(attrs={'class': 'vDateField'}),
    )

    class Meta:
        model = Person
        fields = "__all__"


class TrainingInlineForm(forms.ModelForm):
    training_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=DateInput(attrs={'class': 'vDateField'}),
    )
    next_review_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUTS,
        widget=DateInput(attrs={'class': 'vDateField'}),
    )

    class Meta:
        model = Training
        fields = "__all__"


class InductionInlineForm(forms.ModelForm):
    induction_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=DateInput(attrs={'class': 'vDateField'}),
    )
    next_review_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUTS,
        widget=DateInput(attrs={'class': 'vDateField'}),
    )

    class Meta:
        model = Induction
        fields = "__all__"


class LeaveInlineForm(forms.ModelForm):
    start_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=DateInput(attrs={'class': 'vDateField'}),
    )
    end_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS,
        widget=DateInput(attrs={'class': 'vDateField'}),
    )
    approval_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUTS,
        widget=DateInput(attrs={'class': 'vDateField'}),
    )

    class Meta:
        model = Leave
        fields = "__all__"
