# Vyze - Professional Mental Health Companion API

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
from accounts.decorators import doctor_required, patient_required
from .models import (
    MoodEntry, Journal, Achievement, DoctorNote,
    DoctorPatientAssignment
)
from accounts.models import User
from .serializers import (
    UserSerializer, MoodEntrySerializer, JournalSerializer,
    AchievementSerializer, DoctorNoteSerializer,
    DoctorPatientAssignmentSerializer, DashboardStatsSerializer
)


class CustomAuthToken(ObtainAuthToken):
    """Custom authentication token view"""

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    """User registration endpoint"""
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user(request):
    """Get current user information"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


class MoodEntryViewSet(viewsets.ModelViewSet):
    """Mood Entry API"""
    serializer_class = MoodEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MoodEntry.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class JournalViewSet(viewsets.ModelViewSet):
    """Journal API"""
    serializer_class = JournalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Journal.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    """Achievement API"""
    serializer_class = AchievementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Achievement.objects.filter(user=self.request.user)


class DoctorNoteViewSet(viewsets.ModelViewSet):
    """Doctor Note API"""
    serializer_class = DoctorNoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role == 'doctor':
            return DoctorNote.objects.filter(doctor=self.request.user)
        else:
            return DoctorNote.objects.filter(
                patient=self.request.user,
                is_visible_to_patient=True
            )

    @action(detail=False, methods=['post'], url_path='(?P<patient_id>\d+)')
    def create_for_patient(self, request, patient_id=None):
        """Create a doctor note for a specific patient"""
        if request.user.role != 'doctor':
            return Response(
                {'error': 'Only doctors can create notes'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response(
                {'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if doctor is assigned to this patient
        if not DoctorPatientAssignment.objects.filter(
            doctor=request.user,
            patient=patient,
            is_active=True
        ).exists():
            return Response(
                {'error': 'You are not assigned to this patient'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(doctor=request.user, patient=patient)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    """Get dashboard statistics for the current user"""
    user = request.user

    if user.role == 'patient':
        # Patient dashboard stats
        recent_moods = MoodEntry.objects.filter(user=user).order_by('-date')[:7]
        recent_journals = Journal.objects.filter(user=user).order_by('-date')[:5]
        achievements = Achievement.objects.filter(user=user)
        doctor_notes = DoctorNote.objects.filter(
            patient=user,
            is_visible_to_patient=True
        ).order_by('-date')[:5]

        # Calculate streak
        streak = calculate_streak(user)

        # Get assigned doctors
        assigned_doctors = User.objects.filter(
            assigned_patients__patient=user,
            assigned_patients__is_active=True
        ).distinct()

        # Mood analysis
        mood_analysis = analyze_mood_trends(user)

        stats = {
            'total_moods': MoodEntry.objects.filter(user=user).count(),
            'total_journals': Journal.objects.filter(user=user).count(),
            'current_streak': streak,
            'avg_mood': round(MoodEntry.objects.filter(user=user).aggregate(
                Avg('mood'))['mood__avg'] or 0, 1),
            'mood_distribution': list(MoodEntry.objects.filter(user=user).values('mood').annotate(
                count=Count('id')).order_by('mood')),
            'recent_entries': MoodEntrySerializer(recent_moods, many=True).data,
            'recent_journals': JournalSerializer(recent_journals, many=True).data,
            'achievements': AchievementSerializer(achievements, many=True).data,
            'doctor_notes': DoctorNoteSerializer(doctor_notes, many=True).data,
            'assigned_doctors': UserSerializer(assigned_doctors, many=True).data,
            'mood_analysis': mood_analysis,
        }

    else:
        # Doctor dashboard stats
        assigned_patients = User.objects.filter(
            assigned_doctors__doctor=user,
            assigned_doctors__is_active=True
        ).distinct()

        recent_entries = MoodEntry.objects.filter(
            user__in=assigned_patients
        ).order_by('-date')[:20]

        stats = {
            'patients': UserSerializer(assigned_patients, many=True).data,
            'recent_entries': MoodEntrySerializer(recent_entries, many=True).data,
        }

    return Response(stats)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@doctor_required
def assigned_patients(request):
    """Get patients assigned to the current doctor"""

    patients = User.objects.filter(
        assigned_doctors__doctor=request.user,
        assigned_doctors__is_active=True
    ).distinct()

    serializer = UserSerializer(patients, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@doctor_required
def assign_patient(request):
    """Assign a patient to the current doctor"""

    patient_id = request.data.get('patient_id', '').strip().upper()

    try:
        patient = User.objects.get(patient_id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response(
            {'error': f'No patient found with ID: {patient_id}'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Check if already assigned
    if DoctorPatientAssignment.objects.filter(
        doctor=request.user,
        patient=patient,
        is_active=True
    ).exists():
        return Response(
            {'error': f'Patient {patient.username} is already assigned to you'},
            status=status.HTTP_400_BAD_REQUEST
        )

    assignment = DoctorPatientAssignment.objects.create(
        doctor=request.user,
        patient=patient
    )

    serializer = DoctorPatientAssignmentSerializer(assignment)
    return Response({
        'message': f'Successfully assigned patient {patient.username} (ID: {patient_id})',
        'assignment': serializer.data
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@doctor_required
def patient_details(request, patient_id):
    """Get detailed information about a specific patient"""

    try:
        patient = User.objects.get(id=patient_id, role='patient')
    except User.DoesNotExist:
        return Response(
            {'error': 'Patient not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Check if doctor is assigned to this patient
    if not DoctorPatientAssignment.objects.filter(
        doctor=request.user,
        patient=patient,
        is_active=True
    ).exists():
        return Response(
            {'error': 'You are not assigned to this patient'},
            status=status.HTTP_403_FORBIDDEN
        )

    mood_entries = MoodEntry.objects.filter(user=patient).order_by('-date')
    journals = Journal.objects.filter(user=patient).order_by('-date')

    # Calculate patient statistics
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)

    mood_trend = MoodEntry.objects.filter(
        user=patient,
        date__date__gte=start_date,
        date__date__lte=end_date
    ).order_by('date__date').values('date__date').annotate(
        avg_mood=Avg('mood'),
        count=Count('id')
    )

    mood_distribution = MoodEntry.objects.filter(user=patient).values('mood').annotate(
        count=Count('id')
    ).order_by('mood')

    total_moods = mood_entries.count()
    total_journals = journals.count()
    avg_mood = round(MoodEntry.objects.filter(user=patient).aggregate(Avg('mood'))['mood__avg'] or 0, 1)
    current_streak = calculate_streak(patient)

    data = {
        'patient': UserSerializer(patient).data,
        'mood_entries': MoodEntrySerializer(mood_entries, many=True).data,
        'journals': JournalSerializer(journals, many=True).data,
        'mood_trend': list(mood_trend),
        'mood_distribution': list(mood_distribution),
        'stats': {
            'total_moods': total_moods,
            'total_journals': total_journals,
            'avg_mood': avg_mood,
            'avg_mood_percentage': int(avg_mood * 10),
            'current_streak': current_streak
        }
    }

    return Response(data)


# Helper functions
def calculate_streak(user):
    """Calculate current mood logging streak"""
    today = timezone.now().date()
    streak = 0
    check_date = today

    while True:
        if MoodEntry.objects.filter(user=user, date__date=check_date).exists():
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return streak


def analyze_mood_trends(user):
    """Analyze mood trends for the user"""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_moods = MoodEntry.objects.filter(
        user=user,
        date__gte=thirty_days_ago
    ).order_by('date')

    if not recent_moods.exists():
        return {
            'trend': 'neutral',
            'message': 'Start logging your mood to get personalized insights!',
            'recommendations': ['Log your daily mood', 'Write in your journal', 'Try breathing exercises']
        }

    avg_mood = sum(mood.mood for mood in recent_moods) / len(recent_moods)

    if len(recent_moods) >= 3:
        first_half = recent_moods[:len(recent_moods)//2]
        second_half = recent_moods[len(recent_moods)//2:]

        first_avg = sum(m.mood for m in first_half) / len(first_half) if first_half else avg_mood
        second_avg = sum(m.mood for m in second_half) / len(second_half) if second_half else avg_mood

        trend_slope = second_avg - first_avg
    else:
        trend_slope = 0

    if trend_slope > 0.5:
        trend = 'improving'
        message = 'Your mood has been trending upward! Keep up the great work.'
    elif trend_slope < -0.5:
        trend = 'declining'
        message = 'Your mood has been trending downward. Consider reaching out for support.'
    else:
        trend = 'stable'
        message = 'Your mood has been relatively stable. This is a good foundation to build upon.'

    return {
        'trend': trend,
        'avg_mood': round(avg_mood, 1),
        'message': message,
        'data_points': len(recent_moods)
    }


# Import required modules for aggregation
from django.db.models import Avg, Count