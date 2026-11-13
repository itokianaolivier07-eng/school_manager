"""Écolages : encaissement, reçus PDF, impayés, historique et tarifs."""
import html

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QBrush, QColor, QPageSize, QPdfWriter, QTextDocument
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from app import config
from app.core import school
from app.core.exceptions import AppError
from app.ui.crud_view import CrudView
from app.ui.forms import Field, FormDialog
from app.ui.toast import show_toast
from app.ui.utils import handle_error

STATUS_COLORS = {"Payé": "#dcfce7", "Partiel": "#fef3c7", "Impayé": "#fee2e2", "Gratuit": "#f1f5f9"}


def _item(text, align_right=False):
    it = QTableWidgetItem("" if text is None else str(text))
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if align_right:
        it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return it


def save_receipt_pdf(parent, services, payment_id):
    d = services.payments.receipt_data(payment_id)
    path, _ = QFileDialog.getSaveFileName(parent, "Enregistrer le reçu", f"{d['receipt_no']}.pdf", "PDF (*.pdf)")
    if not path:
        return
    esc = html.escape
    what = school.FEE_ITEM_LABELS[d["fee_code"]]
    cancelled = "<p style='color:#b91c1c'><b>PAIEMENT ANNULÉ</b></p>" if d["cancelled"] else ""
    doc = QTextDocument()
    doc.setHtml(f"""
    <h2 style='color:#312e81'>REÇU DE PAIEMENT</h2><p>N° <b>{esc(d['receipt_no'])}</b> — {esc(d['paid_at'])}</p>{cancelled}
    <hr><p><b>Élève :</b> {esc(d['last_name'])} {esc(d['first_name'])} ({esc(d['matricule'])})<br>
    <b>Classe :</b> {esc(d['class_name'] or '-')} — <b>Année scolaire :</b> {esc(d['school_year'])}</p>
    <p><b>Objet :</b> {esc(what)}<br><b>Mode :</b> {esc(school.METHODS[d['method']])}
    {('<br><b>Référence :</b> ' + esc(d['reference'])) if d['reference'] else ''}</p>
    <h3>Montant : {school.fmt_ar(d['amount'])}</h3>
    <p>Reçu par : {esc(d['cashier'] or '-')}</p>""")
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A5))
    doc.print(writer)
    show_toast(parent, "Reçu PDF enregistré")


class CollectTab(QWidget):
    """Recherche d'un élève -> situation mois par mois -> encaissement."""

    def __init__(self, services, ctx):
        super().__init__()
        self.sv, self.ctx = services, ctx
        self.student_id, self.rows = None, []
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un élève (nom, prénom ou matricule)…")
        self.search.setMaxLength(100)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(config.SEARCH_DEBOUNCE_MS)
        self.timer.timeout.connect(self._search)
        self.search.textChanged.connect(lambda _t: self.timer.start())
        self.results = QListWidget()
        self.results.setObjectName("results")
        self.results.setMaximumHeight(130)
        self.results.itemClicked.connect(self._pick)

        self.header = QLabel("Sélectionnez un élève.")
        self.header.setObjectName("muted")
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Période", "Dû", "Payé", "Reste", "Statut"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.totals = QLabel()
        self.pay_btn = QPushButton("Encaisser")
        self.pay_btn.setProperty("variant", "success")
        self.pay_btn.clicked.connect(self.collect)
        self.pay_btn.setVisible(ctx.session.can("payments.write"))

        bottom = QHBoxLayout()
        bottom.addWidget(self.totals, 1)
        bottom.addWidget(self.pay_btn)
        lay = QVBoxLayout(self)
        lay.addWidget(self.search)
        lay.addWidget(self.results)
        lay.addWidget(self.header)
        lay.addWidget(self.table, 1)
        lay.addLayout(bottom)

    def _search(self):
        self.results.clear()
        text = self.search.text().strip()
        if not text:
            return
        try:
            page = self.sv.students.page(search=text, page=0, size=15)
        except Exception as e:
            return handle_error(self, e)
        for r in page.rows:
            it = QListWidgetItem(f"{r['last_name']} {r['first_name']} — {r['matricule']} — "
                                 f"{r['class_name'] or 'sans classe'}")
            it.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.results.addItem(it)

    def _pick(self, item):
        self.student_id = item.data(Qt.ItemDataRole.UserRole)
        self.load()

    def load(self):
        if self.student_id is None:
            return
        try:
            st = self.sv.payments.statement(self.student_id)
        except Exception as e:
            self.table.setRowCount(0)
            self.header.setText("—")
            self.totals.setText("")
            return handle_error(self, e)
        s = st["student"]
        remise = f" — remise {s['tuition_discount']} %" if s["tuition_discount"] else ""
        self.header.setText(f"<b>{s['last_name']} {s['first_name']}</b> — {s['class_name']} — {s['school_year']}{remise}")
        self.rows = st["rows"]
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            cells = [r["label"], school.fmt_ar(r["due"]), school.fmt_ar(r["paid"]),
                     school.fmt_ar(r["balance"]), r["status"]]
            for j, text in enumerate(cells):
                it = _item(text, align_right=j in (1, 2, 3))
                it.setBackground(QBrush(QColor(STATUS_COLORS[r["status"]])))
                it.setForeground(QBrush(QColor("#1e293b")))
                self.table.setItem(i, j, it)
        self.totals.setText(f"Total dû : <b>{school.fmt_ar(st['total_due'])}</b> — payé : "
                            f"<b>{school.fmt_ar(st['total_paid'])}</b> — reste : "
                            f"<b>{school.fmt_ar(st['total_due'] - st['total_paid'])}</b>")

    def collect(self):
        if self.student_id is None:
            return QMessageBox.information(self, "Écolage", "Sélectionnez d'abord un élève.")
        cur = self.rows[self.table.currentRow()] if 0 <= self.table.currentRow() < len(self.rows) else None
        initial = {"fee_code": cur["fee_code"] if cur else school.MONTH_FEE_CODES[school.SCHOOL_MONTHS[0]],
                   "amount": cur["balance"] if cur else 0, "method": "cash"}
        fields = [
            Field("fee_code", "Poste", "combo", required=True,
                  choices=lambda: [(school.FEE_ITEM_LABELS[k], k) for k in school.FEE_ITEM_CODES]),
            Field("amount", "Montant (Ar)", "number", required=True, minimum=0, maximum=school.MAX_AMOUNT,
                  decimals=0, step=1000),
            Field("method", "Mode de paiement", "combo", required=True,
                  choices=lambda: [(v, k) for k, v in school.METHODS.items()]),
            Field("reference", "Référence (n° transaction, facultatif)", max_len=60)]
        while True:
            dlg = FormDialog("Encaisser un paiement", fields, initial, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            initial = dlg.values()
            try:
                pid, receipt = self.sv.payments.record(self.student_id, initial)
                break
            except AppError as e:
                handle_error(self, e)
            except Exception as e:
                return handle_error(self, e)
        show_toast(self, f"Paiement enregistré — reçu {receipt}")
        self.load()
        if QMessageBox.question(self, "Reçu", "Enregistrer le reçu en PDF ?") == QMessageBox.StandardButton.Yes:
            try:
                save_receipt_pdf(self, self.sv, pid)
            except Exception as e:
                handle_error(self, e)

    def refresh(self):
        self.load()


class ArrearsTab(QWidget):
    def __init__(self, services, ctx):
        super().__init__()
        self.sv = services
        self.class_cb = QComboBox()
        go = QPushButton("Calculer les impayés")
        go.clicked.connect(self.compute)
        top = QHBoxLayout()
        top.addWidget(QLabel("Classe"))
        top.addWidget(self.class_cb, 1)
        top.addWidget(go)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Matricule", "Nom", "Prénom", "Dû à ce jour", "Payé", "Reste"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.total = QLabel()
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.total)

    def refresh(self):
        try:
            current = self.class_cb.currentData()
            self.class_cb.clear()
            for label, val in self.sv.classes.options():
                self.class_cb.addItem(label, val)
            self.class_cb.setCurrentIndex(max(0, self.class_cb.findData(current)))
        except Exception as e:
            handle_error(self, e)

    def compute(self):
        cid = self.class_cb.currentData()
        if cid is None:
            return
        try:
            rows = self.sv.payments.arrears(cid)
        except Exception as e:
            return handle_error(self, e)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(("matricule", "last_name", "first_name", "due", "paid", "balance")):
                v = school.fmt_ar(r[key]) if key in ("due", "paid", "balance") else r[key]
                self.table.setItem(i, j, _item(v, align_right=key in ("due", "paid", "balance")))
        self.total.setText(f"{len(rows)} élève(s) en retard — total des impayés : "
                           f"<b>{school.fmt_ar(sum(r['balance'] for r in rows))}</b>")


class FeesView(QWidget):
    def __init__(self, services, ctx):
        super().__init__()
        self.tabs = QTabWidget()
        self.collect = CollectTab(services, ctx)
        self.arrears = ArrearsTab(services, ctx)
        self.tabs.addTab(self.collect, "Encaissement")
        self.tabs.addTab(self.arrears, "Impayés")

        pay_cols = [("receipt_no", "Reçu"), ("paid_at", "Date"), ("matricule", "Matricule"),
                    ("student_name", "Élève"), ("fee_code", "Poste", school.FEE_ITEM_LABELS),
                    ("amount", "Montant (Ar)"),
                    ("method", "Mode", school.METHODS), ("cancelled", "État", {0: "", 1: "Annulé"})]

        def selected_payment(view):
            row = view.model.row_at(view.table.currentIndex().row())
            if row is None:
                QMessageBox.information(view, "Paiements", "Sélectionnez d'abord un paiement.")
            return row

        def receipt(view):
            row = selected_payment(view)
            if row:
                save_receipt_pdf(view, services, row["id"])

        def cancel(view):
            row = selected_payment(view)
            if not row:
                return
            reason, ok = QInputDialog.getText(view, "Annuler le paiement", f"Motif d'annulation de {row['receipt_no']} :")
            if ok:
                services.payments.cancel(row["id"], reason)
                show_toast(view, "Paiement annulé", "info")
                view.refresh()

        self.history = CrudView(services.payments, pay_cols, [], ctx, noun="paiement", read_only=True,
                                extra_actions=[("Reçu PDF", receipt, "payments.read"),
                                               ("Annuler le paiement", cancel, "payments.cancel")])
        self.tabs.addTab(self.history, "Historique")
        if ctx.session.can("fees.read"):
            amount_fields = [
                ("droit_amount", "Droit"),
                ("photocopy_amount", "Photocopie"),
                ("uniform_amount", "Tenue"),
                ("activity_1_amount", "Activité 1"),
                ("activity_2_amount", "Activité 2"),
                ("activity_3_amount", "Activité 3"),
                ("activity_4_amount", "Activité 4"),
                ("activity_5_amount", "Activité 5"),
            ]
            cols = [("class_name", "Classe"), ("school_year", "Année"),
                    ("monthly_amount", "Écolage mensuel (Ar)")] + [
                        (key, f"{label} (Ar)") for key, label in amount_fields]
            fields = [Field("class_id", "Classe", "combo", required=True,
                            choices=services.fees.class_options),
                      Field("monthly_amount", "Écolage mensuel, septembre à juin (Ar)", "number",
                            required=True, maximum=school.MAX_AMOUNT, decimals=0, step=1000)]
            fields.extend(Field(key, f"{label} (Ar)", "number", maximum=school.MAX_AMOUNT,
                                decimals=0, step=1000, default=0) for key, label in amount_fields)
            self.fees = CrudView(services.fees, cols, fields, ctx, noun="tarif")
            self.tabs.addTab(self.fees, "Tarifs par classe")
        self.tabs.currentChanged.connect(lambda _i: self._refresh_tab())
        lay = QVBoxLayout(self)
        lay.addWidget(self.tabs)

    def _refresh_tab(self):
        w = self.tabs.currentWidget()
        if hasattr(w, "refresh"):
            w.refresh()

    def refresh(self):
        self._refresh_tab()
