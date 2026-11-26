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
        fields = ('customer_name', 'phone', 'comment')
        widgets = {
            'customer_name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'phone': forms.TextInput(
                attrs={'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '+996 ...'}
            ),
            'comment': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Размеры, доставка, удобное время для звонка'}
            ),
        }

    def is_spam(self):
        return bool(self.cleaned_data.get('website'))
