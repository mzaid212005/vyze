from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import MoodEntry, Journal, Achievement, DoctorNote, DoctorPatientAssignment
from .forms import MoodEntryForm, JournalForm
from accounts.models import User
import json
from django.db.models import Count, Avg
from accounts.decorators import doctor_required, patient_required

@login_required
@patient_required
def patient_dashboard(request):

    # Ensure patient ID is generated for existing users
    if not request.user.patient_id or request.user.patient_id == '':
        request.user.patient_id = request.user.generate_patient_id()
        request.user.save()

    # Get recent mood entries
    recent_moods = MoodEntry.objects.filter(user=request.user).order_by('-date')[:7]

    # Calculate streak
    streak = calculate_streak(request.user)

    # Get achievements
    achievements = Achievement.objects.filter(user=request.user)

    # Get recent journals
    recent_journals = Journal.objects.filter(user=request.user).order_by('-date')[:5]

    # Get visible doctor notes
    doctor_notes = DoctorNote.objects.filter(
        patient=request.user,
        is_visible_to_patient=True
    ).order_by('-date')[:5]

    # Get assigned doctors
    assigned_doctors = User.objects.filter(
        assigned_patients__patient=request.user,
        assigned_patients__is_active=True
    ).distinct()

    # AI Mood Analysis
    mood_analysis = analyze_mood_trends(request.user)

    context = {
        'recent_moods': recent_moods,
        'streak': streak,
        'achievements': achievements,
        'recent_journals': recent_journals,
        'doctor_notes': doctor_notes,
        'assigned_doctors': assigned_doctors,
        'patient_id': request.user.patient_id,
        'mood_analysis': mood_analysis,
    }
    return render(request, 'dashboard/patient_dashboard.html', context)

@login_required
def log_mood(request):
    if request.method == 'POST':
        form = MoodEntryForm(request.POST)
        if form.is_valid():
            mood_entry = form.save(commit=False)
            mood_entry.user = request.user
            
            # Process selected tags
            selected_tags = request.POST.get('selected_tags', '')
            mood_entry.tags = selected_tags
            
            mood_entry.save()

            # Check for achievements
            check_achievements(request.user)

            messages.success(request, 'Mood logged successfully!')
            return redirect('patient_dashboard')
    else:
        form = MoodEntryForm()
    return render(request, 'dashboard/log_mood.html', {'form': form})

@login_required
def add_journal(request):
    if request.method == 'POST':
        form = JournalForm(request.POST)
        if form.is_valid():
            journal = form.save(commit=False)
            journal.user = request.user
            journal.save()
            messages.success(request, 'Journal entry added!')
            return redirect('patient_dashboard')
    else:
        form = JournalForm()
    return render(request, 'dashboard/add_journal.html', {'form': form})

from accounts.decorators import doctor_required, patient_required

@login_required
@doctor_required
def doctor_dashboard(request):

    # Get assigned patients only
    assigned_patients = User.objects.filter(
        assigned_doctors__doctor=request.user,
        assigned_doctors__is_active=True
    ).distinct()

    # Get recent mood entries from assigned patients only
    recent_entries = MoodEntry.objects.filter(
        user__in=assigned_patients
    ).order_by('-date')[:20]

    context = {
        'patients': assigned_patients,
        'recent_entries': recent_entries,
    }
    return render(request, 'dashboard/doctor_dashboard.html', context)

@login_required
@doctor_required
def patient_detail(request, patient_id):

    patient = get_object_or_404(User, id=patient_id, role='patient')
    mood_entries = MoodEntry.objects.filter(user=patient).order_by('-date')
    journals = Journal.objects.filter(user=patient).order_by('-date')

    # Calculate patient statistics
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)

    # Mood trend data
    mood_trend = MoodEntry.objects.filter(
        user=patient,
        date__date__gte=start_date,
        date__date__lte=end_date
    ).order_by('date__date').values('date__date').annotate(
        avg_mood=Avg('mood'),
        count=Count('id')
    )

    # Overall statistics
    total_moods = mood_entries.count()
    total_journals = journals.count()
    avg_mood = round(MoodEntry.objects.filter(user=patient).aggregate(Avg('mood'))['mood__avg'] or 0, 1)
    current_streak = calculate_streak(patient)

    # Mood distribution
    mood_distribution = MoodEntry.objects.filter(
        user=patient
    ).values('mood').annotate(
        count=Count('id')
    ).order_by('mood')

    # Convert date objects to strings for JSON serialization
    mood_trend_serializable = []
    for item in mood_trend:
        mood_trend_serializable.append({
            'date__date': item['date__date'].isoformat() if item['date__date'] else None,
            'avg_mood': item['avg_mood'],
            'count': item['count']
        })

    context = {
        'patient': patient,
        'mood_entries': mood_entries,
        'journals': journals,
        'mood_trend': json.dumps(mood_trend_serializable),
        'mood_distribution': list(mood_distribution),
        'patient_stats': {
            'total_moods': total_moods,
            'total_journals': total_journals,
            'avg_mood': avg_mood,
            'avg_mood_percentage': int(avg_mood * 10),
            'current_streak': current_streak
        }
    }
    return render(request, 'dashboard/patient_detail.html', context)

@login_required
@doctor_required
def add_doctor_note(request, patient_id):

    patient = get_object_or_404(User, id=patient_id, role='patient')
    if request.method == 'POST':
        note = request.POST['note']
        is_visible = request.POST.get('is_visible_to_patient', False) == 'on'
        DoctorNote.objects.create(
            patient=patient,
            doctor=request.user,
            note=note,
            is_visible_to_patient=is_visible
        )
        messages.success(request, 'Note added successfully!')
        return redirect('patient_detail', patient_id=patient_id)
    return render(request, 'dashboard/add_note.html', {'patient': patient})

@login_required
@doctor_required
def assign_patient(request):

    if request.method == 'POST':
        patient_id = request.POST.get('patient_id', '').strip().upper()
        try:
            patient = User.objects.get(patient_id=patient_id, role='patient')

            # Check if already assigned
            if DoctorPatientAssignment.objects.filter(
                doctor=request.user,
                patient=patient,
                is_active=True
            ).exists():
                messages.warning(request, f'Patient {patient.username} is already assigned to you.')
            else:
                DoctorPatientAssignment.objects.create(
                    doctor=request.user,
                    patient=patient
                )
                messages.success(request, f'Successfully assigned patient {patient.username} (ID: {patient_id}).')

        except User.DoesNotExist:
            messages.error(request, f'No patient found with ID: {patient_id}')

    return render(request, 'dashboard/assign_patient.html')

@login_required
def progress_analytics(request):
    if request.user.role != 'patient':
        return redirect('doctor_dashboard')

    # Get data for the last 30 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)

    # Mood trend data
    mood_trend = MoodEntry.objects.filter(
        user=request.user,
        date__date__gte=start_date,
        date__date__lte=end_date
    ).order_by('date__date').values('date__date').annotate(
        avg_mood=Avg('mood'),
        count=Count('id')
    )

    # Journal activity
    journal_activity = Journal.objects.filter(
        user=request.user,
        date__date__gte=start_date,
        date__date__lte=end_date
    ).order_by('date__date').values('date__date').annotate(
        count=Count('id')
    )

    # Achievements earned
    recent_achievements = Achievement.objects.filter(
        user=request.user
    ).order_by('-unlocked_at')[:5]

    # Overall statistics
    total_moods = MoodEntry.objects.filter(user=request.user).count()
    total_journals = Journal.objects.filter(user=request.user).count()
    current_streak = calculate_streak(request.user)
    avg_mood = round(MoodEntry.objects.filter(user=request.user).aggregate(Avg('mood'))['mood__avg'] or 0, 1)

    # Mood distribution
    mood_distribution = MoodEntry.objects.filter(
        user=request.user
    ).values('mood').annotate(
        count=Count('id')
    ).order_by('mood')

    # Mood prediction for next week
    mood_prediction = predict_next_week_mood(request.user)

    # Convert date objects to strings for JSON serialization
    mood_trend_serializable = []
    for item in mood_trend:
        mood_trend_serializable.append({
            'date__date': item['date__date'].isoformat() if item['date__date'] else None,
            'avg_mood': item['avg_mood'],
            'count': item['count']
        })

    journal_activity_serializable = []
    for item in journal_activity:
        journal_activity_serializable.append({
            'date__date': item['date__date'].isoformat() if item['date__date'] else None,
            'count': item['count']
        })

    # Calculate percentage for progress bar
    avg_mood_percentage = int(avg_mood * 10)

    # Process mood prediction weekly forecast with percentages
    if mood_prediction and 'weekly_forecast' in mood_prediction:
        mood_prediction['weekly_forecast_with_percentages'] = [
            {'mood': mood, 'mood_percentage': int(mood * 10)}
            for mood in mood_prediction['weekly_forecast']
        ]

    context = {
        'mood_trend': json.dumps(mood_trend_serializable),
        'journal_activity': json.dumps(journal_activity_serializable),
        'recent_achievements': recent_achievements,
        'stats': {
            'total_moods': total_moods,
            'total_journals': total_journals,
            'current_streak': current_streak,
            'avg_mood': avg_mood,
            'avg_mood_percentage': avg_mood_percentage
        },
        'mood_distribution': list(mood_distribution),
        'mood_prediction': mood_prediction
    }

    return render(request, 'dashboard/progress_analytics.html', context)

@login_required
def mini_games(request):
    if request.user.role != 'patient':
        return redirect('doctor_dashboard')
    return render(request, 'dashboard/mini_games.html')

@login_required
def breathing_exercise(request):
    if request.user.role != 'patient':
        return redirect('doctor_dashboard')
    return render(request, 'dashboard/breathing_exercise.html')

@login_required
def positive_quotes(request):
    if request.user.role != 'patient':
        return redirect('doctor_dashboard')

    quotes = [
        "You are stronger than you think.",
        "Every day is a new beginning.",
        "Your mental health matters.",
        "Small steps lead to big changes.",
        "You are not alone in this journey.",
        "Be kind to yourself today.",
        "Your feelings are valid.",
        "Progress, not perfection.",
        "You deserve peace and happiness.",
        "One day at a time."
    ]
    import random
    selected_quote = random.choice(quotes)
    return render(request, 'dashboard/positive_quotes.html', {'quote': selected_quote})

@login_required
def ai_mood_prediction(request):
    if request.user.role != 'patient':
        return redirect('doctor_dashboard')

    # Get user's recent mood data
    recent_moods = MoodEntry.objects.filter(user=request.user).order_by('-date')[:14]  # Last 2 weeks

    prediction_data = None
    if len(recent_moods) >= 7:
        # Simple AI prediction based on patterns
        mood_values = [mood.mood for mood in recent_moods]
        avg_mood = sum(mood_values) / len(mood_values)

        # Trend analysis
        if len(mood_values) >= 7:
            first_half = sum(mood_values[:len(mood_values)//2]) / len(mood_values[:len(mood_values)//2])
            second_half = sum(mood_values[len(mood_values)//2:]) / len(mood_values[len(mood_values)//2:])

            if second_half > first_half:
                trend = "improving"
                trend_message = "Your mood has been trending upward! Keep up the great work."
            elif second_half < first_half:
                trend = "declining"
                trend_message = "Your mood has been trending downward. Consider reaching out for support."
            else:
                trend = "stable"
                trend_message = "Your mood has been relatively stable. This consistency is positive."

            # Generate personalized recommendations
            recommendations = generate_ai_recommendations(avg_mood, trend, request.user)

            prediction_data = {
                'avg_mood': round(avg_mood, 1),
                'trend': trend,
                'trend_message': trend_message,
                'recommendations': recommendations,
                'data_points': len(mood_values),
                'predicted_mood': predict_next_mood(mood_values),
                'confidence': calculate_prediction_confidence(mood_values)
            }

    return render(request, 'dashboard/ai_mood_prediction.html', {
        'prediction_data': prediction_data,
        'recent_moods': recent_moods
    })

@login_required
def crisis_support(request):
    if request.user.role != 'patient':
        return redirect('doctor_dashboard')

    # Emergency contacts and resources
    emergency_contacts = [
        {
            'name': 'National Suicide Prevention Lifeline',
            'number': '988',
            'description': '24/7 support for suicide prevention and mental health crisis'
        },
        {
            'name': 'Crisis Text Line',
            'number': 'Text HOME to 741741',
            'description': 'Free 24/7 crisis counseling via text message'
        },
        {
            'name': 'Emergency Services',
            'number': '911',
            'description': 'For immediate danger or medical emergency'
        }
    ]

    # Mental health resources
    resources = [
        {
            'title': 'Mental Health America',
            'description': 'Screening tools and mental health resources',
            'url': 'https://www.mhanational.org/',
            'icon': 'fas fa-brain'
        },
        {
            'title': 'NAMI (National Alliance on Mental Illness)',
            'description': 'Support for individuals and families affected by mental illness',
            'url': 'https://www.nami.org/',
            'icon': 'fas fa-users'
        },
        {
            'title': 'Psychology Today',
            'description': 'Find therapists and mental health professionals',
            'url': 'https://www.psychologytoday.com/',
            'icon': 'fas fa-user-md'
        }
    ]

    context = {
        'emergency_contacts': emergency_contacts,
        'resources': resources,
    }
    return render(request, 'dashboard/crisis_support.html', context)

@login_required
@patient_required
def emergency_contacts(request):

    # Get user's assigned doctors
    assigned_doctors = User.objects.filter(
        assigned_patients__patient=request.user,
        assigned_patients__is_active=True
    ).distinct()

    context = {
        'assigned_doctors': assigned_doctors,
    }
    return render(request, 'dashboard/emergency_contacts.html', context)

# Helper functions
def calculate_streak(user):
    # Simple streak calculation - consecutive days with mood entries
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

def check_achievements(user):
    # Simple achievement logic
    mood_count = MoodEntry.objects.filter(user=user).count()
    if mood_count >= 7 and not Achievement.objects.filter(user=user, title='Week Warrior').exists():
        Achievement.objects.create(user=user, title='Week Warrior', description='Logged mood for 7 days!', points=10)

    if mood_count >= 30 and not Achievement.objects.filter(user=user, title='Monthly Master').exists():
        Achievement.objects.create(user=user, title='Monthly Master', description='Logged mood for 30 days!', points=50)

def analyze_mood_trends(user):
    """AI-powered mood analysis function"""
    # Get recent mood entries (last 30 days)
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

    # Calculate average mood
    avg_mood = sum(mood.mood for mood in recent_moods) / len(recent_moods)

    # Analyze trend (simple linear regression)
    if len(recent_moods) >= 3:
        # Calculate trend slope
        x_values = list(range(len(recent_moods)))
        y_values = [mood.mood for mood in recent_moods]

        # Simple trend calculation
        if len(recent_moods) > 1:
            first_half = y_values[:len(y_values)//2]
            second_half = y_values[len(y_values)//2:]

            first_avg = sum(first_half) / len(first_half) if first_half else avg_mood
            second_avg = sum(second_half) / len(second_half) if second_half else avg_mood

            trend_slope = second_avg - first_avg
        else:
            trend_slope = 0
    else:
        trend_slope = 0

    # Determine mood trend
    if trend_slope > 0.5:
        trend = 'improving'
        message = 'Your mood has been trending upward! Keep up the great work.'
        recommendations = [
            'Continue your current wellness routine',
            'Consider sharing your progress with your doctor',
            'Try new activities that bring you joy'
        ]
    elif trend_slope < -0.5:
        trend = 'declining'
        message = 'Your mood has been trending downward. Consider reaching out for support.'
        recommendations = [
            'Practice deep breathing exercises',
            'Reach out to your assigned doctor',
            'Try mindfulness activities',
            'Consider professional counseling if needed'
        ]
    else:
        trend = 'stable'
        message = 'Your mood has been relatively stable. This is a good foundation to build upon.'
        recommendations = [
            'Maintain your current routine',
            'Try new wellness activities',
            'Continue journaling your thoughts',
            'Stay connected with your support network'
        ]

    # Mood range analysis
    if avg_mood >= 8:
        mood_level = 'excellent'
        additional_message = 'You\'re doing exceptionally well! Consider how you can maintain this positive state.'
    elif avg_mood >= 6:
        mood_level = 'good'
        additional_message = 'You\'re in a good place. Small improvements can make a big difference.'
    elif avg_mood >= 4:
        mood_level = 'moderate'
        additional_message = 'There\'s room for improvement. Focus on self-care and professional support.'
    else:
        mood_level = 'needs_attention'
        additional_message = 'Consider reaching out to mental health professionals for additional support.'

    return {
        'trend': trend,
        'mood_level': mood_level,
        'avg_mood': round(avg_mood, 1),
        'message': message,
        'additional_message': additional_message,
        'recommendations': recommendations,
        'data_points': len(recent_moods)
    }

def generate_ai_recommendations(avg_mood, trend, user):
    recommendations = []

    if avg_mood < 4:
        recommendations.extend([
            "Consider speaking with a mental health professional",
            "Try daily gratitude journaling to shift perspective",
            "Practice deep breathing exercises for 5 minutes daily",
            "Reach out to trusted friends or family for support"
        ])
    elif avg_mood < 6:
        recommendations.extend([
            "Continue with your current wellness activities",
            "Try adding mindfulness meditation to your routine",
            "Consider light exercise like walking",
            "Track your sleep patterns for better rest"
        ])
    else:
        recommendations.extend([
            "Great job maintaining positive mental health!",
            "Consider helping others by sharing your coping strategies",
            "Try advanced mindfulness techniques",
            "Continue your current healthy habits"
        ])

    if trend == "declining":
        recommendations.insert(0, "⚠️ URGENT: Your mood trend suggests you may need additional support")
        recommendations.insert(1, "Consider contacting a healthcare provider soon")

    # Add personalized recommendations based on user's activity
    journal_count = Journal.objects.filter(user=user).count()
    if journal_count < 5:
        recommendations.append("Try journaling more frequently to process your emotions")

    game_sessions = 0  # This would be tracked in a real implementation
    if game_sessions < 3:
        recommendations.append("Engage with our wellness games for stress relief")

    return recommendations[:5]  # Return top 5 recommendations

def predict_next_mood(mood_values):
    if len(mood_values) < 3:
        return sum(mood_values) / len(mood_values)

    # Simple linear regression for prediction
    n = len(mood_values)
    x_values = list(range(n))
    y_values = mood_values

    # Calculate slope and intercept
    sum_x = sum(x_values)
    sum_y = sum(y_values)
    sum_xy = sum(x * y for x, y in zip(x_values, y_values))
    sum_xx = sum(x * x for x in x_values)

    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
    intercept = (sum_y - slope * sum_x) / n

    # Predict next value
    next_x = n
    predicted = slope * next_x + intercept

    # Ensure prediction is within valid range
    return max(1, min(10, round(predicted, 1)))

def calculate_prediction_confidence(mood_values):
    if len(mood_values) < 5:
        return "Low"

    # Calculate variance as a measure of predictability
    mean = sum(mood_values) / len(mood_values)
    variance = sum((x - mean) ** 2 for x in mood_values) / len(mood_values)
    std_dev = variance ** 0.5

    if std_dev < 1:
        return "High"
    elif std_dev < 2:
        return "Medium"
    else:
        return "Low"

def predict_next_week_mood(user):
    """Simple mood prediction based on recent patterns"""
    # Get last 14 days of mood data
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=14)

    recent_moods = MoodEntry.objects.filter(
        user=user,
        date__date__gte=start_date,
        date__date__lte=end_date
    ).order_by('date__date')

    if not recent_moods.exists():
        return {
            'prediction': 'neutral',
            'confidence': 'low',
            'message': 'Need more mood data for accurate predictions',
            'weekly_forecast': [5, 5, 5, 5, 5, 5, 5]
        }

    # Simple trend analysis
    mood_values = list(recent_moods.values_list('mood', flat=True))
    avg_mood = sum(mood_values) / len(mood_values)

    # Calculate trend (simple linear regression slope)
    if len(mood_values) > 1:
        x_values = list(range(len(mood_values)))
        slope = sum((x - sum(x_values)/len(x_values)) * (y - avg_mood)
                   for x, y in zip(x_values, mood_values)) / sum((x - sum(x_values)/len(x_values))**2 for x in x_values)
    else:
        slope = 0

    # Predict next week's moods
    base_mood = mood_values[-1] if mood_values else 5
    weekly_forecast = []

    for i in range(7):
        predicted_mood = min(10, max(1, base_mood + (slope * (i + 1) * 0.1)))
        weekly_forecast.append(round(predicted_mood, 1))

    # Determine overall prediction
    avg_predicted = sum(weekly_forecast) / len(weekly_forecast)

    if avg_predicted >= 7:
        prediction = 'positive'
        message = 'Your mood trend suggests a positive week ahead!'
    elif avg_predicted >= 4:
        prediction = 'stable'
        message = 'Your mood is likely to remain stable this week.'
    else:
        prediction = 'challenging'
        message = 'You might face some challenging days. Consider reaching out for support.'

    confidence = 'high' if len(mood_values) >= 7 else 'medium' if len(mood_values) >= 3 else 'low'

    return {
        'prediction': prediction,
        'confidence': confidence,
        'message': message,
        'weekly_forecast': weekly_forecast,
        'avg_predicted': round(avg_predicted, 1)
    }
