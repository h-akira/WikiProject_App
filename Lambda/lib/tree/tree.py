#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from django.urls import reverse
from bs4 import BeautifulSoup


class Tree:
  def __init__(self, name, data, upper_slug="", top=True, end=False):
    # dataは/でsplitされたリストを要素に持つリスト（すなわち二次元のリスト）
    self.name = name
    self.end = end
    if top:
      self.slug = ""
    else:
      self.slug = os.path.join(upper_slug, name)
    next_names = []
    next_datas = []
    next_ends = []
    for d in data:
      if d[0] not in next_names:
        next_names.append(d[0])
        next_datas.append([])
        next_ends.append(False)
      if len(d) > 1:
        next_datas[next_names.index(d[0])].append(d[1:])
      else:
        next_ends[next_names.index(d[0])] = True
    self.nexts = []
    for _name, _data, _end in zip(next_names, next_datas, next_ends):
      self.nexts.append(Tree(_name, _data, upper_slug=self.slug, top=False, end=_end))

  def gen_html(self, username, prettify=True, top=True, a_class=None):
    text = ""
    if top:
      text += "<ul>"
    text += "<li>"
    if self.end:
      url = reverse('wiki:detail', args=[username, self.slug])
      if a_class == None:
        text += f'<a href="{url}"> {self.name} </a>'
      else:
        text += f'<a href="{url}" class="{a_class}"> {self.name} </a>'
    else:
      text += self.name
    if len(self.nexts):
      text += "<ul>"
      for next_tree in self.nexts:
        text += next_tree.gen_html(username, prettify=False, top=False, a_class=a_class)
      text += "</ul>"
    text += "</li>"
    if top:
      text += "</ul>"
    if prettify:
      soup = BeautifulSoup(text, "html.parser")
      text = soup.prettify()
    return text

  def gen_obj_list(self, username, User, PageTable):
    obj_list = []
    if self.end:
      user = User.objects.get(username=username)
      obj = PageTable.objects.get(user=user, slug=self.slug)
      obj_list.append(obj)
    if len(self.nexts):
      for next_tree in self.nexts:
        obj_list += next_tree.gen_obj_list(username, User=User, PageTable=PageTable)
    return obj_list


def gen_tree_htmls(request, User, PageTable, a_white=True):
  htmls = []
  users = User.objects.all()
  for user in users:
    if request.user.is_authenticated:
      if user == request.user:
        pages = PageTable.objects.filter(user=user)
      else:
        pages = PageTable.objects.filter(user=user, public=True)
    else:
      pages = PageTable.objects.filter(user=user, public=True)
    pages = pages.order_by('-priority')
    data = []
    for page in pages:
      data.append(page.slug.split("/"))
    tree = Tree(user.username, data=data)
    if a_white:
      htmls.append(tree.gen_html(user.username, a_class="a-white"))
    else:
      htmls.append(tree.gen_html(user.username))
  return htmls


def gen_pages_ordered_by_tree(request, User, PageTable):
  from django.db import models
  pages = PageTable.objects.filter(user=request.user).order_by('-priority')
  data = []
  for page in pages:
    data.append(page.slug.split("/"))
  tree = Tree(request.user.username, data=data)
  page_list = tree.gen_obj_list(request.user.username, User, PageTable)
  page_ids = [i.pk for i in page_list]
  pages = pages.order_by(
    models.Case(
      *[models.When(pk=pk, then=pos) for pos, pk in enumerate(page_ids)]
    )
  )
  return pages
