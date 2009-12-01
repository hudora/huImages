from django import forms


class UploadForm(forms.Form):
    title = forms.CharField(required=False)
    image = forms.ImageField()
