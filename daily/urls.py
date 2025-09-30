"""
URL configuration for daily project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from logs import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('logs/login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('daily_log/', views.daily_log_view, name='daily_log'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('export_logs_excel/', views.export_logs_excel, name='export_logs_excel'),
    path('export_staff_logs/', views.export_staff_logs, name='export_staff_logs'),
    path('add_staff/', views.add_staff, name='add_staff'),
]
