import uuid
from django.db import models
from django.utils import timezone


class CustomUserManager(models.Manager):
  """
  Custom user manager for User model with UUID primary key
  """
  def normalize_email(self, email):
    """Normalize the email address by lowercasing the domain part of it"""
    email = email or ''
    try:
      email_name, domain_part = email.strip().rsplit('@', 1)
    except ValueError:
      pass
    else:
      email = email_name + '@' + domain_part.lower()
    return email

  def create_user(self, username, email, **extra_fields):
    """Create and save a regular user with username and email (Cognito handles password)"""
    if not username:
      raise ValueError('The Username field must be set')
    if not email:
      raise ValueError('The Email field must be set')
    email = self.normalize_email(email)
    user = self.model(username=username, email=email, **extra_fields)
    user.save(using=self._db)
    return user

  def create_superuser(self, username, email, **extra_fields):
    """Create and save a superuser with username and email (Cognito handles password)"""
    extra_fields.setdefault('is_staff', True)
    extra_fields.setdefault('is_superuser', True)

    if extra_fields.get('is_staff') is not True:
      raise ValueError('Superuser must have is_staff=True.')
    if extra_fields.get('is_superuser') is not True:
      raise ValueError('Superuser must have is_superuser=True.')

    return self.create_user(username, email, **extra_fields)


class User(models.Model):
  """
  Custom User model compatible with Aurora DSQL and AWS Cognito
  Uses UUID as primary key instead of auto-incrementing integer
  Does not use PermissionsMixin to avoid contenttypes dependency
  Authentication is handled by Cognito, not Django
  """
  id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
  username = models.CharField(max_length=150, unique=True)
  email = models.EmailField(unique=True)
  first_name = models.CharField(max_length=150, blank=True)
  last_name = models.CharField(max_length=150, blank=True)
  is_active = models.BooleanField(default=True)
  is_staff = models.BooleanField(default=False)
  is_superuser = models.BooleanField(default=False)
  date_joined = models.DateTimeField(default=timezone.now)
  last_login = models.DateTimeField(null=True, blank=True)

  objects = CustomUserManager()

  USERNAME_FIELD = 'username'
  REQUIRED_FIELDS = ['email']

  class Meta:
    db_table = 'users'
    verbose_name = 'user'
    verbose_name_plural = 'users'

  def __str__(self):
    return self.username

  def get_full_name(self):
    """Return the first_name plus the last_name, with a space in between"""
    full_name = f'{self.first_name} {self.last_name}'
    return full_name.strip()

  def get_short_name(self):
    """Return the short name for the user"""
    return self.first_name

  def has_perm(self, perm, obj=None):
    """Simple permission check - superusers have all permissions"""
    return self.is_superuser

  def has_module_perms(self, app_label):
    """Simple permission check - superusers have all permissions"""
    return self.is_superuser

  @property
  def is_authenticated(self):
    """Always return True for authenticated users"""
    return True

  @property
  def is_anonymous(self):
    """Always return False for authenticated users"""
    return False