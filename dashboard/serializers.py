# Vyze - Professional Mental Health Companion Serializers

from rest_framework import serializers
from .models import MoodEntry, Journal, Achievement, DoctorNote, DoctorPatientAssignment
from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """User serializer for API responses"""

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'patient_id',
            'first_name', 'last_name', 'date_of_birth',
            'phone_number', 'date_joined'
        ]
        read_only_fields = ['id', 'date_joined', 'patient_id']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """User serializer for registration"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'role', 'first_name', 'last_name'
        ]

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class MoodEntrySerializer(serializers.ModelSerializer):
    """Mood Entry serializer"""

    class Meta:
        model = MoodEntry
        fields = ['id', 'mood', 'note', 'date']
        read_only_fields = ['id', 'date']


class JournalSerializer(serializers.ModelSerializer):
    """Journal serializer"""

    class Meta:
        model = Journal
        fields = ['id', 'title', 'content', 'date']
        read_only_fields = ['id', 'date']


class AchievementSerializer(serializers.ModelSerializer):
    """Achievement serializer"""

    class Meta:
        model = Achievement
        fields = ['id', 'title', 'description', 'points', 'unlocked_at']
        read_only_fields = ['id', 'unlocked_at']


class DoctorNoteSerializer(serializers.ModelSerializer):
    """Doctor Note serializer"""
    doctor_name = serializers.CharField(source='doctor.username', read_only=True)
    patient_name = serializers.CharField(source='patient.username', read_only=True)

    class Meta:
        model = DoctorNote
        fields = [
            'id', 'patient', 'doctor', 'note', 'date',
            'is_visible_to_patient', 'doctor_name', 'patient_name'
        ]
        read_only_fields = ['id', 'date', 'doctor_name', 'patient_name']


class DoctorPatientAssignmentSerializer(serializers.ModelSerializer):
    """Doctor-Patient Assignment serializer"""
    doctor_name = serializers.CharField(source='doctor.username', read_only=True)
    patient_name = serializers.CharField(source='patient.username', read_only=True)
    patient_id_display = serializers.CharField(source='patient.patient_id', read_only=True)

    class Meta:
        model = DoctorPatientAssignment
        fields = [
            'id', 'doctor', 'patient', 'assigned_date',
            'is_active', 'notes', 'doctor_name',
            'patient_name', 'patient_id_display'
        ]
        read_only_fields = ['id', 'assigned_date', 'doctor_name', 'patient_name', 'patient_id_display']


class DashboardStatsSerializer(serializers.Serializer):
    """Dashboard statistics serializer"""
    total_moods = serializers.IntegerField()
    total_journals = serializers.IntegerField()
    current_streak = serializers.IntegerField()
    avg_mood = serializers.FloatField()
    mood_distribution = serializers.ListField()
    recent_entries = MoodEntrySerializer(many=True)
    recent_journals = JournalSerializer(many=True)
    achievements = AchievementSerializer(many=True)
    doctor_notes = DoctorNoteSerializer(many=True)
    assigned_doctors = UserSerializer(many=True)
    mood_analysis = serializers.DictField()


class MoodAnalysisSerializer(serializers.Serializer):
    """Mood analysis serializer"""
    trend = serializers.CharField()
    avg_mood = serializers.FloatField()
    message = serializers.CharField()
    data_points = serializers.IntegerField()


class GameSessionSerializer(serializers.Serializer):
    """Game session serializer"""
    id = serializers.IntegerField()
    user = serializers.IntegerField()
    game_type = serializers.CharField()
    score = serializers.IntegerField()
    duration = serializers.IntegerField()
    completed_at = serializers.DateTimeField()