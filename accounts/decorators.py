from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def doctor_required(view_func):
    """Decorator to restrict access to doctor users only"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to access this page.')
            return redirect('login')
        
        if request.user.role != 'doctor':
            messages.error(request, 'Access denied. This page is only available to doctors.')
            return redirect('patient_dashboard')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def patient_required(view_func):
    """Decorator to restrict access to patient users only"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to access this page.')
            return redirect('login')
        
        if request.user.role != 'patient':
            messages.error(request, 'Access denied. This page is only available to patients.')
            return redirect('doctor_dashboard')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view