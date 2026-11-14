from app.services.auth_service import AuthService
from app.services.backup_service import BackupService
from app.services.catalog_services import ClassService, TeacherService
from app.services.dashboard_service import DashboardService
from app.services.employee_hr_services import (AttendanceService, SalaryDisbursementService,
                                               SalaryService)
from app.services.fee_service import ExpenseService, FeeService, PaymentService
from app.services.student_service import StudentService
from app.services.user_service import UserService


class Services:
    def __init__(self, ctx):
        self.auth = AuthService(ctx)
        self.students = StudentService(ctx)
        self.teachers = TeacherService(ctx)
        self.classes = ClassService(ctx)
        self.attendance = AttendanceService(ctx)
        self.salaries = SalaryService(ctx)
        self.salary_disbursements = SalaryDisbursementService(ctx)
        self.users = UserService(ctx)
        self.backup = BackupService(ctx)
        self.dashboard = DashboardService(ctx)
        self.fees = FeeService(ctx)
        self.payments = PaymentService(ctx)
        self.expenses = ExpenseService(ctx)
