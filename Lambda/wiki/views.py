from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.urls import reverse
from django.conf import settings
from accounts.decorators import cognito_login_required
from accounts.models import User
from .models import PageTable
from .forms import PageForm, PageSettingsFormSet
from tree import Tree, gen_tree_htmls, gen_pages_ordered_by_tree
from urllib.parse import quote
import random


def index(request):
  """
  Display list of wiki pages with tree navigation
  Shows public pages and user's own pages if authenticated
  """
  if request.user.is_authenticated:
    pages = PageTable.objects.filter(
      Q(public=True) | Q(user=request.user)
    ).order_by("-last_updated")
  else:
    pages = PageTable.objects.filter(public=True).order_by("-last_updated")

  context = {
    "tree_htmls": gen_tree_htmls(request, User, PageTable, a_white=False),
    "nav_tree_htmls": gen_tree_htmls(request, User, PageTable, a_white=True),
    "pages": pages
  }
  return render(request, 'wiki/index.html', context)


def share_detail(request, share_code):
  """
  View a wiki page by share code
  """
  try:
    page = PageTable.objects.get(share_code=share_code)
  except PageTable.DoesNotExist:
    return not_found(request)
  return detail(request, page.user.username, page.slug, share=True)


def detail(request, username, slug, share=False):
  """
  Display a single wiki page with tree navigation

  Args:
    username: Owner's username
    slug: Page slug
    share: Whether accessed via share code
  """
  try:
    user = User.objects.get(username=username)
    page = PageTable.objects.get(user=user, slug=slug)
  except User.DoesNotExist:
    return not_found(request)
  except PageTable.DoesNotExist:
    # If page doesn't exist and user is the owner, redirect to create page
    if request.user.is_authenticated:
      if user == request.user:
        return redirect("wiki:create_with_slug", slug=slug)
      else:
        return not_found(request)
    else:
      return not_found(request)

  # Check permissions
  if not share and not page.public and page.user != request.user:
    return not_found(request)

  # Determine if user can edit
  if page.user == request.user or (request.user.is_authenticated and page.edit_permission):
    edit = True
  else:
    edit = False

  # Generate share URL if sharing is enabled
  if page.share:
    share_url = f"{settings.DOMAIN}{reverse('wiki:share_detail', args=[page.share_code])}"
  else:
    share_url = None

  context = {
    "page": page,
    "username": username,
    "slug": slug,
    "share": share,
    "share_url": share_url,
    "share_code": page.share_code,
    "edit": edit,
    "nav_tree_htmls": gen_tree_htmls(request, User, PageTable, a_white=True),
  }
  return render(request, 'wiki/detail.html', context)


@cognito_login_required
def create(request, slug=None):
  """
  Create a new wiki page with tree navigation

  Args:
    slug: Optional pre-filled slug
  """
  if request.method == 'POST':
    form = PageForm(request.POST)
    if form.is_valid():
      instance = form.save(commit=False)
      instance.user = request.user
      instance.save()

      # Redirect based on action button pressed
      if request.POST['action'] == 'update':
        return redirect("wiki:update", instance.user.username, instance.slug)
      elif request.POST['action'] == 'detail':
        return redirect("wiki:detail", instance.user.username, instance.slug)
      else:
        raise Exception("Invalid action")
  else:
    # Generate random share code
    allow = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    length = 32
    share_code = ''.join(random.choice(allow) for i in range(length))

    form = PageForm(
      initial={
        'slug': slug,
        'share_code': share_code,
      }
    )
    context = {
      "form": form,
      "type": "create",
      "author": True,
      "nav_tree_htmls": gen_tree_htmls(request, User, PageTable, a_white=True),
    }
    return render(request, 'wiki/edit.html', context)


def share_update(request, share_code):
  """
  Update a wiki page accessed via share code
  """
  try:
    page = PageTable.objects.get(share_code=share_code)
  except PageTable.DoesNotExist:
    return not_found(request)
  return update(request, page.user.username, page.slug, share=True)


def not_found(request, message="ページが見つかりません"):
  """
  Display not found page
  """
  context = {
    "message": message,
  }
  return render(request, 'wiki/not_found.html', context)


@cognito_login_required
def update(request, username, slug, share=False):
  """
  Update an existing wiki page with tree navigation

  Args:
    username: Owner's username
    slug: Page slug
    share: Whether accessed via share code
  """
  try:
    user = User.objects.get(username=username)
  except User.DoesNotExist:
    return not_found(request)

  try:
    page = PageTable.objects.get(user=user, slug=slug)
  except PageTable.DoesNotExist:
    return redirect("wiki:create_with_slug", slug=slug)

  # Check edit permissions
  if page.user == request.user or page.edit_permission:
    if request.method == 'POST':
      form = PageForm(request.POST, instance=page)
      if form.is_valid():
        form.save()

        # Redirect based on action button pressed
        if request.POST['action'] == 'update':
          if share:
            return redirect("wiki:share_update", page.share_code)
          else:
            return redirect("wiki:update", username, form.instance.slug)
        elif request.POST['action'] == 'detail':
          if share:
            return redirect("wiki:share_detail", page.share_code)
          else:
            return redirect("wiki:detail", username, form.instance.slug)
        else:
          raise Exception("Invalid action")
    else:
      # Determine if user is the author
      if page.user == request.user:
        author = True
      else:
        author = False

      form = PageForm(instance=page)
      context = {
        "id": page.id,
        "username": username,
        "slug": slug,
        "form": form,
        "type": "update",
        "author": author,
        "share": share,
        "share_code": page.share_code,
        "nav_tree_htmls": gen_tree_htmls(request, User, PageTable, a_white=True),
      }
      return render(request, 'wiki/edit.html', context)
  else:
    return redirect("wiki:index")


@cognito_login_required
def delete(request, id):
  """
  Delete a wiki page

  Args:
    id: Page ID
  """
  page = get_object_or_404(PageTable, pk=id)
  if request.user == page.user or page.edit_permission:
    page.delete()
  return redirect("wiki:index")


@cognito_login_required
def page_settings(request):
  """
  Bulk edit page settings with tree-ordered pages
  Allows users to update multiple pages at once
  """
  if request.method == "POST":
    pages = PageTable.objects.filter(user=request.user)
    formset = PageSettingsFormSet(request.POST, queryset=pages)
    if formset.is_valid():
      formset.save()

      # Redirect based on action button pressed
      if request.POST['action'] == 'continue':
        return redirect("wiki:page_settings")
      elif request.POST['action'] == 'end':
        return redirect("wiki:index")
      else:
        raise Exception("Invalid action")
    else:
      print("---- Error ----")
      print("formset.errors:")
      print(formset.errors)
      print("formset.management_form.errors:")
      print(formset.management_form.errors)
      print("---------------")
      raise Exception("Form validation failed")
  else:
    # Get pages ordered by tree hierarchy
    pages = gen_pages_ordered_by_tree(request, User, PageTable)
    formset = PageSettingsFormSet(queryset=pages)
    context = {
      "formset": formset,
      "pages": pages,
      "nav_tree_htmls": gen_tree_htmls(request, User, PageTable, a_white=True),
    }
    return render(request, 'wiki/page_settings.html', context)
