"""
Models — apps.addons.questions (UC-QST-01..04).

Identifiers + field names in English per DEC-DOC-005.

ProductQuestion — pregunta hecha sobre un producto. El usuario puede
estar autenticado (asker_user) o no (asker_name + asker_email).

Estados (moderacion):
    PENDING   — registrada, pendiente de respuesta y aprobacion.
    ANSWERED  — respondida por admin. Puede o no estar aprobada todavia.
    REJECTED  — rechazada por moderacion; no se muestra publicamente.

Visibilidad publica: ANSWERED con answer_body no vacio.
"""
from django.conf import settings
from django.db import models
from apps.core.models import SoftDeleteModel, TimeStampedModel



class QuestionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pendiente'
    ANSWERED = 'ANSWERED', 'Respondida'
    REJECTED = 'REJECTED', 'Rechazada'


class ProductQuestion(TimeStampedModel, SoftDeleteModel):
    """Pregunta sobre un producto.

    Hereda de SoftDeleteModel (DEC-DOC-007): un DELETE del admin
    conserva la pregunta para auditoria de moderacion (UC-QST-04).
    El estado ``REJECTED`` representa rechazo de NEGOCIO (no se muestra
    al publico) — independiente del ``is_deleted`` (sistema).
    """

    product = models.ForeignKey(
        'catalogue.Product',
        on_delete=models.CASCADE,
        related_name='questions',
    )
    asker_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_questions',
    )
    asker_name = models.CharField(max_length=120, blank=True, default='')
    asker_email = models.EmailField(blank=True, default='')

    body = models.TextField()

    status = models.CharField(
        max_length=16,
        choices=QuestionStatus.choices,
        default=QuestionStatus.PENDING,
    )

    answer_body = models.TextField(blank=True, default='')
    answered_at = models.DateTimeField(null=True, blank=True)
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_questions_answered',
    )

    class Meta:
        db_table = 'questions_productquestion'
        ordering = ['-created_at']
        verbose_name = 'Pregunta de producto'
        verbose_name_plural = 'Preguntas de producto'
        indexes = [
            models.Index(fields=['product', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'Q#{self.pk} product={self.product_id} ({self.status})'


class QuestionModerationLog(TimeStampedModel):
    """Registro de auditoria de cada decision de moderacion (UC-QST-04).

    Toda decision (aprobar/rechazar) queda registrada con quien la tomo,
    cuando y — en rechazos — el motivo. Implementa POST "Registra la accion
    en auditoria" y RNF "Cada pregunta tiene registro de quien la modero y
    cuando".
    """

    APPROVE = 'APPROVE'
    REJECT = 'REJECT'
    ACTION_CHOICES = [(APPROVE, 'Aprobar'), (REJECT, 'Rechazar')]

    question = models.ForeignKey(
        ProductQuestion,
        on_delete=models.CASCADE,
        related_name='moderation_logs',
    )
    action = models.CharField(max_length=8, choices=ACTION_CHOICES)
    reason = models.TextField(blank=True, default='')
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='question_moderations',
    )

    class Meta:
        db_table = 'questions_moderationlog'
        ordering = ['-created_at']
        verbose_name = 'Registro de moderacion de pregunta'
        verbose_name_plural = 'Registros de moderacion de preguntas'
        indexes = [
            models.Index(fields=['question', '-created_at']),
        ]

    def __str__(self):
        return f'ModLog#{self.pk} q={self.question_id} {self.action}'
