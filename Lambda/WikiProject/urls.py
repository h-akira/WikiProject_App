"""
URL configuration for WikiProject project.

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
import os
from django.urls import path
from django.http import JsonResponse

# Check if DSQL mode is enabled
USE_DSQL = os.environ.get('USE_DSQL', 'false').lower() == 'true'


def health_check(request):
  """Simple health check endpoint"""
  return JsonResponse({'status': 'ok'})


urlpatterns = [
  path('health/', health_check, name='health_check'),
]

# Only include admin in non-DSQL mode (local development)
if not USE_DSQL:
  from django.contrib import admin
  urlpatterns.append(path('admin/', admin.site.urls))
