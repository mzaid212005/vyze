from django.db import models
from accounts.models import User

class DoctorPatientAssignment(models.Model):
    doctor = models.ForeignKey(User, related_name='assigned_patients', on_delete=models.CASCADE, limit_choices_to={'role': 'doctor'})
    patient = models.ForeignKey(User, related_name='assigned_doctors', on_delete=models.CASCADE, limit_choices_to={'role': 'patient'})
    assigned_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, help_text="Internal notes about the assignment")

    class Meta:
        unique_together = ['doctor', 'patient']
        ordering = ['-assigned_date']

    def __str__(self):
        return f"Dr. {self.doctor.username} → {self.patient.username} ({self.patient.patient_id})"

class MoodEntry(models.Model):
    MOOD_CHOICES = [(i, f"{i}/10") for i in range(1, 11)]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    mood = models.IntegerField(choices=MOOD_CHOICES)
    note = models.TextField(blank=True)
    tags = models.CharField(max_length=200, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.mood} on {self.date}"

    def get_visible_doctors(self):
        """Get doctors who can view this mood entry"""
        return DoctorPatientAssignment.objects.filter(
            patient=self.user,
            is_active=True
        ).values_list('doctor', flat=True)

class Journal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Achievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    points = models.IntegerField(default=0)
    unlocked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class DoctorNote(models.Model):
    patient = models.ForeignKey(User, related_name='patient_notes', on_delete=models.CASCADE)
    doctor = models.ForeignKey(User, related_name='doctor_notes', on_delete=models.CASCADE)
    note = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    is_visible_to_patient = models.BooleanField(default=True, help_text="Whether patient can see this note")

    def __str__(self):
        return f"Note for {self.patient.username} by {self.doctor.username}"
