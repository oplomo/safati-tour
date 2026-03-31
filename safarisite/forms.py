from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Tour

User = get_user_model()


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Your full name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+254 ...'}),
    )
    inquiry_type = forms.ChoiceField(
        choices=(
            ('general', 'General Question'),
            ('custom', 'Custom Tour Request'),
            ('group', 'Group Booking'),
            ('corporate', 'Corporate Event'),
        ),
    )
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'What would you like help with?'}),
    )
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'rows': 6,
                'placeholder': 'Tell us the trip idea, dates, destinations, or support you need.',
            }
        ),
    )


class BlogCommentForm(forms.Form):
    guest_name = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Your name'}),
    )
    content = forms.CharField(
        max_length=1200,
        widget=forms.Textarea(
            attrs={
                'rows': 4,
                'placeholder': 'Share a thought, ask a question, or reply to the conversation.',
            }
        ),
    )


class BookingRequestForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Your full name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+254 ...'}),
    )
    tour = forms.ModelChoiceField(
        queryset=Tour.objects.filter(is_active=True).order_by('title'),
        empty_label='Select a tour',
    )
    preferred_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    number_of_people = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'placeholder': '2'}),
    )
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'rows': 5,
                'placeholder': 'Tell us your travel dates, special requests, preferred destinations, or anything we should know.',
            }
        ),
    )


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Username',
                'autocomplete': 'username',
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Password',
                'autocomplete': 'current-password',
            }
        ),
    )


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Last name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+254 ...'}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'password1',
            'password2',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(
            {
                'placeholder': 'Choose a username',
                'autocomplete': 'username',
            }
        )
        self.fields['password1'].widget.attrs.update(
            {
                'placeholder': 'Create a password',
                'autocomplete': 'new-password',
            }
        )
        self.fields['password2'].widget.attrs.update(
            {
                'placeholder': 'Confirm password',
                'autocomplete': 'new-password',
            }
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.phone_number = self.cleaned_data.get('phone_number', '')
        if commit:
            user.save()
        return user
