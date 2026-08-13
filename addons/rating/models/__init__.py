"""Modelos del addon ``rating`` (reseñas de producto sobre Odoo rating)."""
from .review import Review, ReviewModerationLog, ReviewHelpfulVote, ReviewImage

__all__ = ['Review', 'ReviewModerationLog', 'ReviewHelpfulVote', 'ReviewImage']
