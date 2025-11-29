from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from mdeditor.fields import MDTextField


class PageTable(models.Model):
  """
  Wiki page model for storing user-created wiki pages

  DSQL Compatibility Notes:
  - ForeignKey is supported (constraint creation is automatically skipped by aurora-dsql-django adapter)
  - Referential integrity must be maintained at application level
  - Uses default auto-incrementing ID (DSQL supports SERIAL)
  """
  # Foreign key to custom User model (UUID primary key)
  # Note: DSQL doesn't enforce foreign key constraints at database level
  user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    related_name='wiki_pages',
    db_constraint=False  # Explicit: no database constraint (DSQL doesn't support it)
  )

  # Timestamps
  last_updated = models.DateTimeField(auto_now=True)

  # Page identification
  slug = models.CharField(max_length=127, db_index=True)
  priority = models.FloatField(default=0)
  title = models.CharField(max_length=127)

  # Visibility and permissions
  public = models.BooleanField(default=False)
  edit_permission = models.BooleanField(default=False)

  # Sharing settings
  share = models.BooleanField(default=False)
  share_edit_permission = models.BooleanField(default=False)
  share_code = models.CharField(
    max_length=127,
    null=True,
    blank=True,
    validators=[RegexValidator(r'^[a-zA-Z0-9]+$')],
    unique=True
  )

  # Content (using MDTextField for markdown editing)
  text = MDTextField(null=True, blank=True)

  def clean(self):
    """Validate model constraints"""
    if self.edit_permission and not self.public:
      raise ValidationError("編集許可をTrueにするには公開もTrueにする必要があります．")
    if self.share_edit_permission and not self.share:
      raise ValidationError("共有編集をTrueにするには共有もTrueにする必要があります．")

  def save(self, *args, **kwargs):
    """Override save to run validation"""
    self.clean()
    super().save(*args, **kwargs)

  def __str__(self):
    return self.title

  class Meta:
    db_table = 'wiki_pages'
    constraints = [
      models.UniqueConstraint(
        fields=["user", "slug"],
        name="wiki_slug_unique"
      )
    ]
    indexes = [
      models.Index(fields=['user', '-last_updated']),
      models.Index(fields=['public', '-last_updated']),
      models.Index(fields=['share_code']),
    ]
