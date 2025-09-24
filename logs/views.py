from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User as DjangoUser
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime, time
import openpyxl
import io
from logs.forms import StaffRegistrationForm
from mongoengine.queryset.visitor import Q

# Import the lazy connection function - DO NOT import models here
from daily.settings import ensure_mongo_connection

def get_mongo_models():
    """Lazy import of MongoEngine models - call this in each view"""
    ensure_mongo_connection()
    from logs.mongo_models import User, DailyLog, EmployeeProfile
    return User, DailyLog, EmployeeProfile

def login_view(request):
    # Get models inside the view function
    User, DailyLog, EmployeeProfile = get_mongo_models()
    
    if request.method == 'POST':
        login_type = request.POST.get('login_type')

        if login_type == 'admin':
            admin_id = request.POST.get('admin_id')
            password = request.POST.get('password')

            if admin_id == 'admin' and password == 'admin123':
                user = authenticate(request, username='admin', password='admin123')
                if user:
                    login(request, user)
                    return redirect('admin_dashboard')
                else:
                    # Create admin user if it doesn't exist
                    if not DjangoUser.objects.filter(username='admin').exists():
                        DjangoUser.objects.create_superuser('admin', 'admin@example.com', 'admin123')
                        user = authenticate(request, username='admin', password='admin123')
                        if user:
                            login(request, user)
                            return redirect('admin_dashboard')
                    messages.error(request, 'Admin authentication failed')
            else:
                messages.error(request, 'Invalid Admin Credentials')

        else:  # Employee login
            id_card_number = request.POST.get('id_card')
            password = request.POST.get('password')

            try:
                profile = EmployeeProfile.objects.get(id_card_number=id_card_number)
                mongo_user = profile.user

                django_user = DjangoUser.objects.filter(username=mongo_user.username).first()

                if django_user:
                    user = authenticate(request, username=django_user.username, password=password)
                    if user:
                        login(request, user)
                        return redirect('daily_log')
                    else:
                        messages.error(request, 'Invalid password')
                else:
                    messages.error(request, 'Django user not found')
            except EmployeeProfile.DoesNotExist:
                messages.error(request, 'User does not exist')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')

    return render(request, 'logs/login.html')

@login_required
def admin_dashboard(request):
    # Get models inside the view function
    User, DailyLog, EmployeeProfile = get_mongo_models()
    
    staff_name = request.GET.get('staff_name', '')
    date = request.GET.get('date', '')

    if not date:
        date = timezone.now().date().isoformat()

    try:
        logs = DailyLog.objects(date=date)

        if staff_name:
            mongo_users = User.objects(
                Q(username__icontains=staff_name) |
                Q(first_name__icontains=staff_name) |
                Q(last_name__icontains=staff_name)
            )
            logs = logs.filter(employee__in=mongo_users)

        context = {
            'logs': logs.order_by('-date', 'time_interval'),
            'staff_name': staff_name,
            'date': date,
        }
        return render(request, 'logs/admin_dashboard.html', context)
    except Exception as e:
        messages.error(request, f'Error loading dashboard: {str(e)}')
        context = {
            'logs': [],
            'staff_name': staff_name,
            'date': date,
        }
        return render(request, 'logs/admin_dashboard.html', context)

@login_required
def daily_log_view(request):
    # Get models inside the view function
    User, DailyLog, EmployeeProfile = get_mongo_models()
    
    today = timezone.now().date()
    time_intervals = generate_time_intervals(today)

    try:
        mongo_user = User.objects(username=request.user.username).first()

        if request.method == 'POST':
            time_interval = request.POST.get('time_interval')
            description = request.POST.get('description')
            status = request.POST.get('status')

            if time_interval and description and mongo_user:
                DailyLog.objects(
                    employee=mongo_user,
                    date=today,
                    time_interval=time_interval
                ).update_one(
                    set__description=description,
                    set__status=status,
                    upsert=True
                )
                messages.success(request, 'Log entry saved successfully')
                return redirect('daily_log')

        logs = DailyLog.objects(employee=mongo_user, date=today).order_by('time_interval') if mongo_user else []

        context = {
            'time_intervals': time_intervals,
            'logs': logs,
            'today': today.strftime('%d %B, %Y'),
        }
        return render(request, 'logs/daily_log.html', context)
    except Exception as e:
        messages.error(request, f'Error loading daily log: {str(e)}')
        context = {
            'time_intervals': time_intervals,
            'logs': [],
            'today': today.strftime('%d %B, %Y'),
        }
        return render(request, 'logs/daily_log.html', context)

def generate_time_intervals(date):
    intervals = []
    if date.weekday() == 5:  # Saturday
        start_hour, end_hour = 9, 14
    else:
        start_hour, end_hour = 8, 17

    for hour in range(start_hour, end_hour):
        for minute in [0, 30]:
            if hour == end_hour - 1 and minute == 30:  # Last interval
                continue

            start_time = time(hour, minute)
            end_minute, end_hour_adjusted = minute + 30, hour
            if end_minute == 60:
                end_minute, end_hour_adjusted = 0, hour + 1

            end_time = time(end_hour_adjusted, end_minute)
            interval_str = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
            intervals.append(interval_str)
    return intervals

def export_logs_excel(request):
    # Get models inside the view function
    User, DailyLog, EmployeeProfile = get_mongo_models()
    
    try:
        logs = DailyLog.objects()

        staff_name = request.GET.get('staff_name', '')
        date = request.GET.get('date', '')

        if staff_name:
            mongo_users = User.objects(
                Q(username__icontains=staff_name) |
                Q(first_name__icontains=staff_name) |
                Q(last_name__icontains=staff_name)
            )
            logs = logs.filter(employee__in=mongo_users)

        if date:
            logs = logs.filter(date=date)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Staff Logs"
        ws.append(['Staff Name', 'Date', 'Time Interval', 'Description', 'Status'])

        for log in logs:
            staff_name_val = (
                f"{log.employee.first_name} {log.employee.last_name}".strip()
                if log.employee else "Unknown"
            )
            ws.append([
                staff_name_val or log.employee.username,
                str(log.date),
                log.time_interval,
                log.description,
                log.status
            ])

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        export_date = date if date else timezone.now().date().isoformat()
        filename = f"staff_logs_{export_date}.xlsx"

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    except Exception as e:
        return HttpResponse(f"Error generating Excel file: {str(e)}", status=500)

def add_staff(request):
    # Get models inside the view function
    User, DailyLog, EmployeeProfile = get_mongo_models()
    
    if request.method == 'POST':
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            # Check if username or email already exists in Django or Mongo
            if User.objects(username=form.cleaned_data['username']).first() or DjangoUser.objects.filter(username=form.cleaned_data['username']).exists():
                messages.error(request, "Username already exists.")
            elif User.objects(email=form.cleaned_data['email']).first() or DjangoUser.objects.filter(email=form.cleaned_data['email']).exists():
                messages.error(request, "Email already exists.")
            else:
                try:
                    # Create Django user (for authentication)
                    django_user = DjangoUser.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name']
                    )
                    # Create MongoEngine user
                    user = User(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name']
                    )
                    user.save()
                    profile = EmployeeProfile(
                        user=user,
                        id_card_number=form.cleaned_data['id_card_number']
                    )
                    profile.save()
                    messages.success(request, "Staff added successfully!")
                    return redirect('add_staff')
                except Exception as e:
                    messages.error(request, f"Error adding staff: {str(e)}")
    else:
        form = StaffRegistrationForm()
    return render(request, 'logs/add_staff.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')