"""
Models — apps.reviews (P-14 / UC-REV-01..03).

Review: una reseña por (user, product). Inherits SoftDeleteModel para
conservar historial de moderación (auditoría RNF-AUDIT-001).

ReviewModerationLog: append-only audit trail. NO hereda SoftDeleteModel
(DEC-DOC-007 exception para tablas de auditoría).

ReviewHelpfulVote: voto de "util" por usuario/reseña (UC-REV-02
FR-REV-02.02). Append-only; unique_together garantiza un voto por
usuario por reseña. Incrementa Review.helpful_count.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from apps.core.models import SoftDeleteModel, TimeStampedModel



class Review(TimeStampedModel, SoftDeleteModel):
    """Reseña de un producto comprado. UC-REV-01..03."""
    STATUS_PENDING  = 'PENDING_MODERATION'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUSES = [
        (STATUS_PENDING,  'Pendiente de moderación'),
        (STATUS_APPROVED, 'Aprobada'),
        (STATUS_REJECTED, 'Rechazada'),
    ]

    REJECT_INAPPROPRIATE = 'CONTENIDO_INAPROPIADO'
    REJECT_SPAM          = 'SPAM'
    REJECT_LANGUAGE      = 'LANGUAGE_NOT_SUPPORTED'
    REJECT_UNRELATED     = 'NO_RELACIONADA'
    REJECT_REASONS = [
        (REJECT_INAPPROPRIATE, 'Contenido inapropiado'),
        (REJECT_SPAM,          'Spam'),
        (REJECT_LANGUAGE,      'Idioma no soportado'),
        (REJECT_UNRELATED,     'No relacionada con el producto'),
    ]

    user    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='reviews',
    )
    product = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
        related_name='reviews',
    )
    order   = models.ForeignKey(
        'orders.Order', on_delete=models.PROTECT,
        related_name='reviews',
        help_text='Orden que prueba la compra (UC-REV-02).',
    )
    rating  = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    title   = models.CharField(max_length=120)
    body    = models.TextField(max_length=2000)
    status  = models.CharField(
        max_length=22, choices=STATUSES,
        default=STATUS_PENDING, db_index=True,
    )
    reject_reason = models.CharField(
        max_length=24, choices=REJECT_REASONS,
        blank=True, default='',
    )
    moderated_at  = models.DateTimeField(null=True, blank=True)
    moderated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='moderated_reviews',
    )
    # UC-REV-02 FR-REV-02.02: votos de 'util' acumulados.
    # Increment-only; decrementos no en scope (deduplicacion via
    # ReviewHelpfulVote unique_together).
    helpful_count = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        db_table        = 'reviews_review'
        unique_together = [('user', 'product')]
        ordering        = ['-created_at']
        verbose_name    = 'Reseña'

    def __str__(self):
        return f'{self.user.username} → {self.product.name} ({self.rating}/5)'


class ReviewModerationLog(TimeStampedModel):
    """
    Append-only audit log of review moderation actions (RNF-AUDIT-001).

    DEC-DOC-007 exception — auditoria append-only no hereda SoftDeleteModel.
    """
    ACTION_APPROVE = 'APPROVE'
    ACTION_REJECT  = 'REJECT'
    ACTIONS = [
        (ACTION_APPROVE, 'Aprobar'),
        (ACTION_REJECT,  'Rechazar'),
    ]

    review     = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name='moderation_logs',
    )
    action     = models.CharField(max_length=10, choices=ACTIONS)
    reason     = models.CharField(max_length=24, blank=True, default='')
    actor      = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        db_table     = 'reviews_moderation_log'
        ordering     = ['-created_at']
        verbose_name = 'Auditoria de moderacion'


class ReviewHelpfulVote(TimeStampedModel):
    """
    Voto de 'util' para una reseña (UC-REV-02 FR-REV-02.02).

    Un voto por (user, review). unique_together garantiza deduplicacion
    a nivel de BD. Cada creacion incrementa Review.helpful_count via
    ReviewHelpfulVoteView (F() expression, atomica).
    """
    user   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='helpful_votes',
    )
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE,
        related_name='helpful_votes',
    )

    class Meta:
        db_table        = 'reviews_helpful_vote'
        unique_together = [('user', 'review')]
        verbose_name    = 'Voto util'

    def __str__(self):
        return f'{self.user.username} -> review#{self.review_id}'
