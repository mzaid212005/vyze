from django import forms
from .models import MoodEntry, Journal

class MoodEntryForm(forms.ModelForm):
    class Meta:
        model = MoodEntry
        fields = ['mood', 'note']
        widgets = {
            'mood': forms.NumberInput(attrs={'min': 1, 'max': 10, 'type': 'range'}),
            'note': forms.Textarea(attrs={'rows': 3, 'placeholder': 'How are you feeling today?'}),
        }

class JournalForm(forms.ModelForm):
    class Meta:
        model = Journal
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Journal Title'}),
            'content': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Write your thoughts...'}),
        }