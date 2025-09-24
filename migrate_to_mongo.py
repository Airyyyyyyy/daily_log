# migrate_to_mongo.py
import os
import sys
import django
import json
from datetime import datetime
from bson import ObjectId

# Setup Django environment
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'daily.settings')
django.setup()

# Now import your MongoEngine models
from logs.mongo_models import User, EmployeeProfile, DailyLog
from django.contrib.auth.models import User as DjangoUser  # Original Django users

def migrate_users():
    """Migrate Django users to MongoEngine User documents"""
    print("Migrating users...")
    
    django_users = DjangoUser.objects.all()
    user_map = {}  # Store mapping: old_user_id -> new_user_id
    
    for django_user in django_users:
        if not django_user.email or '@' not in django_user.email:
            print(f"Skipping user {django_user.username}: invalid email")
            continue

        # Check if user already exists in MongoDB
        existing_user = User.objects(username=django_user.username).first()
        if existing_user:
            print(f"User {django_user.username} already exists in MongoDB")
            user_map[django_user.id] = existing_user.id
            continue
            
        # Create new User document
        mongo_user = User(
            username=django_user.username,
            email=django_user.email,
            first_name=django_user.first_name,
            last_name=django_user.last_name,
            is_active=django_user.is_active,
            is_staff=django_user.is_staff,
            date_joined=django_user.date_joined,
            password='set_a_default_or_hash_here'  # <-- Insert a valid password here!
        )
        mongo_user.save()
        user_map[django_user.id] = mongo_user.id
        print(f"Migrated user: {django_user.username}")
    
    return user_map

def migrate_employee_profiles(user_map):
    """Migrate EmployeeProfile data"""
    print("\nMigrating employee profiles...")
    
    try:
        # Try to load from JSON backup first
        datadump_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datadump.json')
        if os.path.exists(datadump_path) and os.path.getsize(datadump_path) > 0:
            with open('datadump.json', 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
        else:
            print("datadump.json is missing or empty!")
            data = []
        
        profile_count = 0
        for item in data:
            if item['model'] == 'logs.employeeprofile':
                old_user_id = item['fields']['user']
                if old_user_id in user_map:
                    # Check if profile already exists
                    existing_profile = EmployeeProfile.objects(id_card_number=item['fields']['id_card_number']).first()
                    if existing_profile:
                        print(f"Profile with card {item['fields']['id_card_number']} already exists")
                        continue
                    
                    # FIX: Get the actual User document, not just the ID
                    mongo_user = User.objects(id=user_map[old_user_id]).first()
                    if mongo_user:
                        profile = EmployeeProfile(
                            user=mongo_user,  # Pass the document, not the ID
                            id_card_number=item['fields']['id_card_number']
                        )
                        profile.save()
                        profile_count += 1
                        print(f"Migrated profile: {item['fields']['id_card_number']}")
        
        return profile_count
        
    except FileNotFoundError:
        print("No datadump.json found, trying Django ORM...")
        from logs.models import EmployeeProfile as DjangoEmployeeProfile
        
        profile_count = 0
        for django_profile in DjangoEmployeeProfile.objects.all():
            if django_profile.user.id in user_map:
                # Check if profile already exists
                existing_profile = EmployeeProfile.objects(id_card_number=django_profile.id_card_number).first()
                if existing_profile:
                    print(f"Profile with card {django_profile.id_card_number} already exists")
                    continue
                
                # FIX: Get the actual User document
                mongo_user = User.objects(id=user_map[django_profile.user.id]).first()
                if mongo_user:
                    profile = EmployeeProfile(
                        user=mongo_user,  # Pass the document, not the ID
                        id_card_number=django_profile.id_card_number
                    )
                    profile.save()
                    profile_count += 1
                    print(f"Migrated profile: {django_profile.id_card_number}")
        
        return profile_count
    
def migrate_daily_logs(user_map):
    """Migrate DailyLog data"""
    print("\nMigrating daily logs...")
    
    try:
        # Load from JSON backup
        with open('datadump.json', 'r') as f:
            data = json.load(f)
        
        log_count = 0
        for item in data:
            if item['model'] == 'logs.dailylog':
                old_employee_id = item['fields']['employee']
                if old_employee_id in user_map:
                    # FIX: Get the actual User document for the query
                    mongo_employee = User.objects(id=user_map[old_employee_id]).first()
                    if not mongo_employee:
                        continue
                    
                    # Check if log already exists
                    existing_log = DailyLog.objects(
                        employee=mongo_employee,  # Use document, not ID
                        date=datetime.strptime(item['fields']['date'], '%Y-%m-%d').date(),
                        time_interval=item['fields']['time_interval']
                    ).first()
                    
                    if existing_log:
                        print(f"Log already exists for {item['fields']['date']} - {item['fields']['time_interval']}")
                        continue
                    
                    # Parse date and time
                    log_date = datetime.strptime(item['fields']['date'], '%Y-%m-%d').date()                   
                    # Parse created_at (handle different formats)
                    try:
                        created_at = datetime.strptime(item['fields']['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except ValueError:
                        try:
                            created_at = datetime.strptime(item['fields']['created_at'], '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            created_at = datetime.now()
                    
                    log = DailyLog(
                        employee=mongo_employee,  # Use document, not ID
                        date=log_date,
                        time_interval=item['fields']['time_interval'],
                        description=item['fields']['description'],
                        status=item['fields']['status'],
                        created_at=created_at
                    )
                    log.save()
                    log_count += 1
                    print(f"Migrated log: {item['fields']['date']} - {item['fields']['time_interval']}")
        
        return log_count
        
    except FileNotFoundError:
        print("No datadump.json found, trying Django ORM...")
        from logs.models import DailyLog as DjangoDailyLog
        
        log_count = 0
        for django_log in DjangoDailyLog.objects.all():
            if django_log.employee.id in user_map:
                # FIX: Get the actual User document
                mongo_employee = User.objects(id=user_map[django_log.employee.id]).first()
                if not mongo_employee:
                    continue
                
                # Check if log already exists
                existing_log = DailyLog.objects(
                    employee=mongo_employee,  # Use document, not ID
                    date=django_log.date,
                    time_interval=django_log.time_interval
                ).first()
                
                if existing_log:
                    print(f"Log already exists for {django_log.date} - {django_log.time_interval}")
                    continue
                
                log = DailyLog(
                    employee=mongo_employee,  # Use document, not ID
                    date=django_log.date,
                    time_interval=django_log.time_interval,
                    description=django_log.description,
                    status=django_log.status,
                    created_at=django_log.created_at
                )
                log.save()
                log_count += 1
                print(f"Migrated log: {django_log.date} - {django_log.time_interval}")
        
        return log_count
    
def verify_migration():
    """Verify that migration was successful"""
    print("\nVerifying migration...")
    
    # Count documents
    user_count = User.objects.count()
    profile_count = EmployeeProfile.objects.count()
    log_count = DailyLog.objects.count()
    
    print(f"Users in MongoDB: {user_count}")
    print(f"EmployeeProfiles in MongoDB: {profile_count}")
    print(f"DailyLogs in MongoDB: {log_count}")
    
    # Test some queries
    try:
        # Test user retrieval
        test_user = User.objects.first()
        if test_user:
            print(f"Test user: {test_user.username}")
        
        # Test profile retrieval
        test_profile = EmployeeProfile.objects.first()
        if test_profile:
            print(f"Test profile: {test_profile.id_card_number}")
        
        # Test log retrieval
        test_log = DailyLog.objects.first()
        if test_log:
            print(f"Test log: {test_log.description[:50]}...")
        
        print("✓ Migration verification successful!")
        
    except Exception as e:
        print(f"✗ Migration verification failed: {e}")

def cleanup_duplicates():
    """Clean up any duplicate documents"""
    print("\nCleaning up duplicates...")
    
    # Remove duplicate users (keep first occurrence)
    usernames = set()
    duplicates = []
    
    for user in User.objects.all():
        if user.username in usernames:
            duplicates.append(user.id)
        else:
            usernames.add(user.username)
    
    if duplicates:
        User.objects(id__in=duplicates).delete()
        print(f"Removed {len(duplicates)} duplicate users")
    
    # Remove duplicate employee profiles
    card_numbers = set()
    duplicate_profiles = []
    
    for profile in EmployeeProfile.objects.all():
        if profile.id_card_number in card_numbers:
            duplicate_profiles.append(profile.id)
        else:
            card_numbers.add(profile.id_card_number)
    
    if duplicate_profiles:
        EmployeeProfile.objects(id__in=duplicate_profiles).delete()
        print(f"Removed {len(duplicate_profiles)} duplicate profiles")

def main():
    """Main migration function"""
    print("Starting MongoDB migration...")
    print("=" * 50)
    
    try:
        # Step 1: Migrate users
        user_map = migrate_users()
        
        # Step 2: Migrate employee profiles
        profile_count = migrate_employee_profiles(user_map)
        
        # Step 3: Migrate daily logs
        log_count = migrate_daily_logs(user_map)
        
        # Step 4: Clean up duplicates
        cleanup_duplicates()
        
        # Step 5: Verify migration
        verify_migration()
        
        print("\n" + "=" * 50)
        print("Migration completed successfully!")
        print(f"Summary:")
        print(f"- Users migrated: {len(user_map)}")
        print(f"- Employee profiles migrated: {profile_count}")
        print(f"- Daily logs migrated: {log_count}")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()