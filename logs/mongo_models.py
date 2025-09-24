from mongoengine import Document, fields
import datetime

class User(Document):
    username = fields.StringField(required=True, unique=True)
    email = fields.EmailField(required=True, unique=True)
    password = fields.StringField(required=True)
    first_name = fields.StringField()
    last_name = fields.StringField()
    is_active = fields.BooleanField(default=True)
    is_staff = fields.BooleanField(default=False)
    date_joined = fields.DateTimeField()

    meta = {
        'collection': 'auth_user',
        'indexes': ['username', 'email'],
        'ordering': ['username']
    }

    def __str__(self):
        return self.username


class EmployeeProfile(Document):
    user = fields.ReferenceField(User, required=True)  # ✅ proper ReferenceField
    id_card_number = fields.StringField(max_length=20, unique=True, required=True)

    meta = {
        'collection': 'logs_employeeprofile',
        'indexes': ['id_card_number', 'user'],  # ✅ use "user", not "user_id"
        'ordering': ['id_card_number']
    }

    def __str__(self):
        return f"{self.user.username} - {self.id_card_number}"  # ✅ readable


class DailyLog(Document):
    STATUS_CHOICES = [
        ('Ongoing', 'Ongoing'),
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
    ]

    employee = fields.ReferenceField(User, required=True)  # ✅ Reference instead of employee_id
    date = fields.DateTimeField(default=datetime.datetime.utcnow)
    time_interval = fields.StringField(max_length=20, required=True)
    description = fields.StringField(required=True)
    status = fields.StringField(choices=[s[0] for s in STATUS_CHOICES], default='Ongoing')
    created_at = fields.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = fields.DateTimeField(default=datetime.datetime.utcnow)

    meta = {
        'collection': 'logs_dailylog',
        'indexes': [
            'employee',
            'date',
            'time_interval',
            {'fields': ['employee', 'date', 'time_interval'], 'unique': True}
        ],
        'ordering': ['-date', '-created_at']
    }

    def __str__(self):
        return f"{self.employee.username} - {self.date.strftime('%Y-%m-%d')} - {self.time_interval}"

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)
