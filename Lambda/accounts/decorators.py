"""
Custom decorators for Cognito authentication
Replacement for Django's @login_required in DSQL mode
"""
from functools import wraps
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render


def cognito_login_required(view_func):
  """
  Decorator for views that checks if user is authenticated via Cognito

  Usage:
    @cognito_login_required
    def my_view(request):
      # request.user is guaranteed to exist here
      return JsonResponse({'user': request.user.email})
  """
  @wraps(view_func)
  def wrapper(request, *args, **kwargs):
    if not request.user:
      # Check if this is an API request (Accept: application/json)
      accept_header = request.headers.get('Accept', '')
      if 'application/json' in accept_header or request.path.startswith('/api/'):
        return JsonResponse({
          'error': 'Authentication required',
          'detail': 'Please provide a valid Cognito JWT token in Authorization header or id_token cookie'
        }, status=401)

      # Return HTML error page for browser requests
      html = '''
      <!DOCTYPE html>
      <html>
      <head>
        <title>Authentication Required</title>
        <style>
          body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
          .error-box { background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 20px; border-radius: 5px; }
          h1 { color: #721c24; }
          a { color: #007bff; text-decoration: none; }
        </style>
      </head>
      <body>
        <div class="error-box">
          <h1>🔒 Authentication Required</h1>
          <p>This page requires AWS Cognito authentication.</p>
          <p>Please provide a valid JWT token via:</p>
          <ul>
            <li>Authorization header: <code>Bearer &lt;token&gt;</code></li>
            <li>Cookie: <code>id_token=&lt;token&gt;</code></li>
          </ul>
          <p><a href="/">← Back to Home</a></p>
        </div>
      </body>
      </html>
      '''
      return HttpResponse(html, status=401)

    return view_func(request, *args, **kwargs)

  return wrapper


def cognito_superuser_required(view_func):
  """
  Decorator for views that require superuser status

  Usage:
    @cognito_superuser_required
    def admin_view(request):
      return JsonResponse({'message': 'Admin only'})
  """
  @wraps(view_func)
  def wrapper(request, *args, **kwargs):
    if not request.user:
      return JsonResponse({
        'error': 'Authentication required',
        'detail': 'Please provide a valid Cognito JWT token in Authorization header or id_token cookie'
      }, status=401)

    if not request.user.is_superuser:
      return JsonResponse({
        'error': 'Permission denied',
        'detail': 'Superuser access required'
      }, status=403)

    return view_func(request, *args, **kwargs)

  return wrapper


def cognito_staff_required(view_func):
  """
  Decorator for views that require staff status

  Usage:
    @cognito_staff_required
    def staff_view(request):
      return JsonResponse({'message': 'Staff only'})
  """
  @wraps(view_func)
  def wrapper(request, *args, **kwargs):
    if not request.user:
      return JsonResponse({
        'error': 'Authentication required',
        'detail': 'Please provide a valid Cognito JWT token in Authorization header or id_token cookie'
      }, status=401)

    if not request.user.is_staff:
      return JsonResponse({
        'error': 'Permission denied',
        'detail': 'Staff access required'
      }, status=403)

    return view_func(request, *args, **kwargs)

  return wrapper
