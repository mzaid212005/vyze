# Vyze - Professional Mental Health Companion API URLs

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'mood-entries', api.MoodEntryViewSet, basename='mood-entry')
router.register(r'journals', api.JournalViewSet, basename='journal')
router.register(r'achievements', api.AchievementViewSet, basename='achievement')
router.register(r'doctor-notes', api.DoctorNoteViewSet, basename='doctor-note')

# API URL patterns
urlpatterns = [
    # Authentication endpoints
    path('auth/login/', api.CustomAuthToken.as_view(), name='api_login'),
    path('auth/register/', api.register_user, name='api_register'),
    path('auth/user/', api.current_user, name='api_current_user'),

    # Dashboard endpoints
    path('dashboard/stats/', api.dashboard_stats, name='api_dashboard_stats'),

    # Doctor endpoints
    path('doctor/assigned-patients/', api.assigned_patients, name='api_assigned_patients'),
    path('doctor/assign-patient/', api.assign_patient, name='api_assign_patient'),
    path('doctor/patients/<int:patient_id>/', api.patient_details, name='api_patient_details'),

    # Include router URLs
    path('', include(router.urls)),
]