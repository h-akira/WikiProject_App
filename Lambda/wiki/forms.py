from django import forms
from django.forms import modelformset_factory
from .models import PageTable


class PageForm(forms.ModelForm):
  """Form for creating and editing wiki pages"""
  class Meta:
    model = PageTable
    fields = (
      "slug",
      "priority",
      "public",
      "edit_permission",
      "title",
      "text",
      "share",
      "share_code",
      "share_edit_permission"
    )
    widgets = {
      'title': forms.TextInput(
        attrs={
          'style': 'width: 100%; height: auto; font-size: 2rem;'
        }
      ),
      'slug': forms.TextInput(
        attrs={
          'style': 'width: 500px;'
        }
      ),
      'share_code': forms.TextInput(
        attrs={
          'style': 'width: 500px;'
        }
      ),
    }


class PageSettingsForm(forms.ModelForm):
  """Form for bulk editing page settings"""
  class Meta:
    model = PageTable
    fields = ["title", "slug", "priority", "public", "edit_permission"]
    widgets = {
      'title': forms.TextInput(attrs={'style': 'width: 300px;'}),
      'slug': forms.TextInput(attrs={'style': 'width: 220px;'}),
      'priority': forms.NumberInput(attrs={"step": "0.1", "style": "width:70px;"}),
    }


PageSettingsFormSet = modelformset_factory(
  PageTable,
  form=PageSettingsForm,
  extra=0
)
