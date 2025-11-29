"""
Custom context processors for accounts app
Provides user context without django.contrib.auth dependency
"""


def user(request):
  """
  Add user to template context

  This is a simplified version of django.contrib.auth.context_processors.auth
  that works without django.contrib.auth being in INSTALLED_APPS
  """
  return {
    'user': getattr(request, 'user', None)
  }
