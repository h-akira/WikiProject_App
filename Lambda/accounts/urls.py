from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
  # HTML pages
  path('login/', views.login_page, name='login'),
  path('logout/', views.logout_page, name='logout'),
  path('signup/', views.signup_page, name='signup'),
  path('confirm/', views.confirm_page, name='confirm'),

  # API endpoints
  path('api/login/', views.api_login, name='api_login'),
  path('api/signup/', views.api_signup, name='api_signup'),
  path('api/confirm/', views.api_confirm, name='api_confirm'),
  path('api/resend-code/', views.api_resend_code, name='api_resend_code'),
  path('api/current-user/', views.current_user, name='current_user'),

  # Admin endpoints
  path('api/users/', views.user_list, name='user_list'),

  # Health check
  path('health/', views.health_check, name='health_check'),
]
