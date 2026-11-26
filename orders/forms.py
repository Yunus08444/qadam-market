from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):
    # Hidden from people with CSS; simple bots fill every field they see
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'hp-field', 'tabindex': '-1', 'autocomplete': 'off'}
        ),
    )

    class Meta:
        model = Order
        fields = (
            'customer_name', 'phone', 'extra_phone',
            'region', 'locality', 'address', 'comment',
        )
        widgets = {
            'customer_name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'phone': forms.TextInput(
                attrs={'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '+996 ...'}
            ),
            'extra_phone': forms.TextInput(
                attrs={'inputmode': 'tel', 'placeholder': 'Если есть второй номер'}
            ),
            'locality': forms.TextInput(attrs={'placeholder': 'Например: Кызыл-Кия'}),
            'address': forms.TextInput(attrs={'placeholder': 'Улица, дом'}),
            'comment': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Удобное время для звонка, пожелания'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional in the database (orders from WhatsApp), required on the website
        self.fields['customer_name'].required = True

    def clean(self):
        cleaned = super().clean()
        region = cleaned.get('region')
        if region and region != Order.Region.PICKUP and not cleaned.get('locality'):
            self.add_error('locality', 'Укажите район, город или село для доставки')
        return cleaned

    def is_spam(self):
        return bool(self.cleaned_data.get('website'))

    def customer_data(self):
        return {field: self.cleaned_data[field] for field in self.Meta.fields}
