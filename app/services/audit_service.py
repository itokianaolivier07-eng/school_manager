from app.repositories.repos import AuditRepository
from app.services.base import CrudService


class AuditService(CrudService):
    """Lecture seule (le journal n'est modifiable que par les autres services)."""
    entity = "audit"
    repo_cls = AuditRepository
    read_perm = "audit.read"
    default_desc = True
