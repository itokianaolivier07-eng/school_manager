from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.backup_service import BackupService
from app.services.catalog_services import ClassService, SubjectService, TeacherService
from app.services.dashboard_service import DashboardService
from app.services.fee_service import FeeService, PaymentService
from app.services.grade_service import GradeService
from app.services.student_service import StudentService
from app.services.user_service import UserService


class Services:
    """Conteneur : une seule instance de chaque service, partageant le même contexte."""

    def __init__(self, ctx):
        self.auth = AuthService(ctx)
        self.students = StudentService(ctx)
        self.teachers = TeacherService(ctx)
        self.classes = ClassService(ctx)
        self.subjects = SubjectService(ctx)
        self.grades = GradeService(ctx)
        self.users = UserService(ctx)
        self.audit = AuditService(ctx)
        self.backup = BackupService(ctx)
        self.dashboard = DashboardService(ctx)
        self.fees = FeeService(ctx)
        self.payments = PaymentService(ctx)
