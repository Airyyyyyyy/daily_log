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
from logs.mongo_models import User
from logs.forms import StaffRegistrationForm
from mongoengine.queryset.visitor import Q
from logs.mongo_models import DailyLog, EmployeeProfile, User as MongoUser


def login_view(request):
    if request.method == 'POST':
        login_type = request.POST.get('login_type')

        if login_type == 'admin':
            admin_id = request.POST.get('admin_id')
            password = request.POST.get('password')

            if admin_id == 'admin' and password == 'admin123':
                # Create or get Django user for admin
                django_user, created = DjangoUser.objects.get_or_create(
                    username='admin',
                    defaults={
                        'email': 'admin@example.com',
                        'first_name': 'Admin',
                        'last_name': 'User',
                        'is_staff': True,
                        'is_superuser': True
                    }
                )
                if created:
                    django_user.set_password('admin123')
                    django_user.save()

                # Authenticate and login using Django
                user = authenticate(request, username='admin', password='admin123')
                if user:
                    login(request, user)
                    return redirect('admin_dashboard')
                else:
                    messages.error(request, 'Admin authentication failed')
            else:
                messages.error(request, 'Invalid Admin Credentials')

        else: 
            id_card_number = request.POST.get('id_card')
            password = request.POST.get('password')

            try:
                # Find employee profile by ID card number
                profile = EmployeeProfile.objects.get(id_card_number=id_card_number)
                mongo_user = profile.user

                if mongo_user.password == password:
                    # Create or get Django user for session management
                    django_user, created = DjangoUser.objects.get_or_create(
                        username=mongo_user.username,
                        defaults={
                            'email': mongo_user.email,
                            'first_name': mongo_user.first_name,
                            'last_name': mongo_user.last_name
                        }
                    )
                    if created:
                        django_user.set_password(password)
                        django_user.save()

                    # Authenticate and login using Django
                    user = authenticate(request, username=mongo_user.username, password=password)
                    if user:
                        login(request, user)
                        return redirect('daily_log')
                    else:
                        messages.error(request, 'Authentication failed')
                else:
                    messages.error(request, 'Invalid credentials')
            except EmployeeProfile.DoesNotExist:
                messages.error(request, 'User does not exist')

    return render(request, 'logs/login.html')

@login_required
def admin_dashboard(request):
    id_card = request.GET.get('id_card', '')
    date = request.GET.get('date', '')

    if not date:
        date = timezone.now().date().isoformat()

    logs = DailyLog.objects(date=date)

    if id_card:
        try:
            profile = EmployeeProfile.objects.get(id_card_number=id_card)
            mongo_user = profile.user
            logs = logs.filter(employee=mongo_user)
        except EmployeeProfile.DoesNotExist:
            logs = DailyLog.objects.none()
            messages.error(request, f'No staff found with ID Card number: {id_card}')

    context = {
        'logs': logs.order_by('-date', 'time_interval'),
        'id_card': id_card,
        'date': date,
    }
    return render(request, 'logs/admin_dashboard.html', context)

@login_required
def daily_log_view(request):
    selected_date_str = request.GET.get('date', '')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()
    
    # Check if the selected date is in the past
    today = timezone.now().date()
    is_previous_day = selected_date < today
    
    time_intervals = generate_time_intervals(selected_date)

    # Get the Mongo user
    mongo_user = MongoUser.objects(username=request.user.username).first()

    if not mongo_user:
        messages.error(request, 'User profile not found. Please contact administrator.')
        context = {
            'time_intervals': time_intervals,
            'logs': [],
            'today': selected_date.strftime('%d %B, %Y'),
            'selected_date': selected_date.isoformat(),
            'user': {'first_name': 'User', 'last_name': ''},
            'is_previous_day': is_previous_day,
        }
        return render(request, 'logs/daily_log.html', context)

    if request.method == 'POST':
        if is_previous_day:
            messages.error(request, 'Cannot modify logs for previous days.')
            return redirect(f'{request.path}?date={selected_date}')
        
        time_interval = request.POST.get('time_interval')
        description = request.POST.get('description')
        status = request.POST.get('status')

        if time_interval and description and mongo_user:
            DailyLog.objects(
                employee=mongo_user,
                date=selected_date,
                time_interval=time_interval
            ).update_one(
                set__description=description,
                set__status=status,
                upsert=True
            )
            messages.success(request, 'Log entry saved successfully')
            return redirect(f'{request.path}?date={selected_date}')

    # Get logs for the selected date
    logs = DailyLog.objects(employee=mongo_user, date=selected_date).order_by('time_interval')

    # Format date with ordinal suffix
    day = selected_date.day
    day_str = str(day).lstrip('0')
    
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    
    # Format the month and year
    month_year = selected_date.strftime('%B, %Y')
    formatted_date = f"{day_str}{suffix} {month_year}"

    context = {
        'time_intervals': time_intervals,
        'logs': logs,
        'today': formatted_date,
        'selected_date': selected_date.isoformat(),
        'user': mongo_user,
        'is_previous_day': is_previous_day,
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
            if hour == end_hour and minute == 30:
                continue
            start_time = time(hour, minute)
            end_minute, end_hour_adjusted = minute + 30, hour
            if end_minute == 60:
                end_minute, end_hour_adjusted = 0, hour + 1

            end_time = time(end_hour_adjusted, end_minute)
            interval_str = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
            intervals.append(interval_str)
    return intervals

@login_required
def export_logs_excel(request):
    logs = DailyLog.objects()

    id_card = request.GET.get('id_card', '')
    date = request.GET.get('date', '')

    staff_name_for_filename = ""
    
    if id_card:
        try:
            profile = EmployeeProfile.objects.get(id_card_number=id_card)
            mongo_user = profile.user
            logs = logs.filter(employee=mongo_user)
            staff_name_for_filename = f"{mongo_user.first_name}_{mongo_user.last_name}" if mongo_user.first_name and mongo_user.last_name else mongo_user.username
        except EmployeeProfile.DoesNotExist:
            logs = DailyLog.objects.none()

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
            log.date.strftime('%Y-%m-%d') if hasattr(log, 'date') and log.date else '',
            log.time_interval,
            log.description,
            log.status
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # Generate filename based on whether it's for a specific staff or for the day
    if staff_name_for_filename and date:
        filename = f"logs_{staff_name_for_filename}_{date}.xlsx"
    elif staff_name_for_filename:
        filename = f"logs_{staff_name_for_filename}_{timezone.now().date().isoformat()}.xlsx"
    elif date:
        filename = f"all_staff_logs_{date}.xlsx"
    else:
        filename = f"all_staff_logs_{timezone.now().date().isoformat()}.xlsx"

    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@login_required
def export_staff_logs(request):
    # Get the current logged-in user's Mongo user
    mongo_user = MongoUser.objects(username=request.user.username).first()
    
    if not mongo_user:
        messages.error(request, 'User profile not found. Please contact administrator.')
        return redirect('daily_log')
    
    # Get the employee profile to access ID card number
    try:
        profile = EmployeeProfile.objects.get(user=mongo_user)
        id_card_number = profile.id_card_number
    except EmployeeProfile.DoesNotExist:
        id_card_number = "N/A"
        messages.warning(request, 'ID card number not found in profile')
    
    # Get filter parameters from request
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    date = request.GET.get('date', '') 
    
    # Get the current logged-in user's first name
    current_user = request.user
    user_first_name = current_user.first_name if current_user.first_name else current_user.username
    
    # Start with logs only for the current user
    logs = DailyLog.objects(employee=mongo_user).order_by('-date', 'time_interval')
    
    # Apply date filters
    if date:
        logs = logs.filter(date=date)
    elif start_date and end_date:
        logs = logs.filter(date__gte=start_date, date__lte=end_date)
    
    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "My Daily Logs"
    
    headers = ['Staff Name', 'ID Card Number', 'Date', 'Time Interval', 'Description', 'Status']
    ws.append(headers)
    
    # Add data rows
    for log in logs:
        staff_name_val = f"{mongo_user.first_name} {mongo_user.last_name}".strip()
        if not staff_name_val:
            staff_name_val = mongo_user.username
            
        ws.append([
            staff_name_val,
            id_card_number,
            log.date.strftime('%Y-%m-%d') if hasattr(log, 'date') and log.date else '',
            log.time_interval,
            log.description,
            log.status,           
        ])
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Create response
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    # Generate filename with current user's first name and ID card number
    if date:
        filename = f"my_logs_{user_first_name}_{date}.xlsx"
    elif start_date and end_date:
        filename = f"my_logs_{user_first_name}_{start_date}_to_{end_date}.xlsx"
    else:
        filename = f"my_logs_{user_first_name}_{timezone.now().date().isoformat()}.xlsx"
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@login_required
def add_staff(request):
    if request.method == 'POST':
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            if User.objects(username=form.cleaned_data['username']).first() or DjangoUser.objects.filter(username=form.cleaned_data['username']).exists():
                messages.error(request, "Username already exists.")
            elif User.objects(email=form.cleaned_data['email']).first() or DjangoUser.objects.filter(email=form.cleaned_data['email']).exists():
                messages.error(request, "Email already exists.")
            else:
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
                return redirect('admin_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    
    return redirect('admin_dashboard')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')