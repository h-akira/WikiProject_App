"""
Custom template tags for wiki app
Provides utility filters like zip for template operations
"""
from django import template

register = template.Library()


@register.filter
def zip(list1, list2):
  """
  Zip two lists together in templates

  Usage: {% for item1, item2 in list1|zip:list2 %}

  Args:
    list1: First list/queryset
    list2: Second list/queryset

  Returns:
    Zipped iterator of tuples
  """
  return zip(list1, list2)
