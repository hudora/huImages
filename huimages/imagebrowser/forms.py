from django import forms

class UploadForm(forms.Form):
    image = forms.ImageField()
