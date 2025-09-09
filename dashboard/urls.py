from django.urls import path
from . import views

urlpatterns = [
    path('patient/', views.patient_dashboard, name='patient_dashboard'),
    path('doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('assign-patient/', views.assign_patient, name='assign_patient'),
    path('log-mood/', views.log_mood, name='log_mood'),
    path('add-journal/', views.add_journal, name='add_journal'),
    path('progress-analytics/', views.progress_analytics, name='progress_analytics'),
    path('mini-games/', views.mini_games, name='mini_games'),
    path('breathing-exercise/', views.breathing_exercise, name='breathing_exercise'),
    path('positive-quotes/', views.positive_quotes, name='positive_quotes'),
    path('crisis-support/', views.crisis_support, name='crisis_support'),
    path('emergency-contacts/', views.emergency_contacts, name='emergency_contacts'),
    path('ai-mood-prediction/', views.ai_mood_prediction, name='ai_mood_prediction'),
    path('patient/<int:patient_id>/', views.patient_detail, name='patient_detail'),
    path('patient/<int:patient_id>/add-note/', views.add_doctor_note, name='add_doctor_note'),
]