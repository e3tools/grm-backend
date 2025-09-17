from django import forms


class PasswordResetRequestForm(forms.Form):
    """Form to request a password reset by email."""

    email = forms.EmailField(label="Email", max_length=254)
