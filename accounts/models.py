from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    ROLE_CHOICES = [
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patient')
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)

    # Patient ID for doctor assignment
    patient_id = models.CharField(max_length=8, unique=True, blank=True, null=True)

    # Doctor profile fields
    specialization = models.CharField(max_length=100, blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    years_experience = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        # Generate patient ID for patients
        if self.role == 'patient' and (not self.patient_id or self.patient_id == ''):
            self.patient_id = self.generate_patient_id()
        super().save(*args, **kwargs)

    def generate_patient_id(self):
        """Generate a unique 8-character patient ID"""
        while True:
            patient_id = str(uuid.uuid4())[:8].upper()
            if not User.objects.filter(patient_id=patient_id).exists():
                return patient_id

    def __str__(self):
        if self.role == 'patient' and self.patient_id:
            return f"{self.username} (ID: {self.patient_id})"
        return self.username
