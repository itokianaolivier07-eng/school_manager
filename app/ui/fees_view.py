"""Écolages : encaissement, reçus PDF, impayés, historique et tarifs."""
import html

from PyQt6.QtCore import QSignalBlocker, QTimer, Qt
from PyQt6.QtGui import QBrush, QColor, QPageSize, QPdfWriter, QTextDocument
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog,
                             QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                             QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from app import config
from app.core import school
from app.core.exceptions import AppError
from app.ui import theme
from app.ui.crud_view import CrudView
from app.ui.forms import Field, FormDialog
from app.ui.toast import show_toast
from app.ui.utils import LABELS, ask_confirmation, handle_error


def _status_colors(status):
    """Couleurs de statut issues de la palette active (cohérentes clair/sombre)."""
    pal = theme.current_palette()
    return {
        "Payé": (pal["status_paid_bg"], pal["status_paid_text"]),
        "Partiel": (pal["status_partial_bg"], pal["status_partial_text"]),
        "Impayé": (pal["status_due_bg"], pal["status_due_text"]),
        "Gratuit": (pal["status_free_bg"], pal["status_free_text"]),
    }.get(status, (pal["card"], pal["text"]))


def _replace_combo_items(combo, items, selected):
    blocker = QSignalBlocker(combo)
    combo.clear()
    for label, value in items:
        combo.addItem(label, value)
    index = combo.findData(selected)
    if index < 0 and combo.count():
        index = 0
    if index >= 0:
        combo.setCurrentIndex(index)
    value = combo.currentData()
    del blocker
    return value


def _item(text):
    it = QTableWidgetItem("" if text is None else str(text))
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    it.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
    <h2 style='color:#312e81'>REÇU DE PAIEMENT</h2><p>N° <b>{esc(d['receipt_no'])}</b> - {esc(d['paid_at'])}</p>{cancelled}
    <hr><p><b>Élève :</b> {esc(d['last_name'])} {esc(d['first_name'])} ({esc(d['matricule'])})<br>
    <b>Classe :</b> {esc(d['class_name'] or '-')} - <b>Année scolaire :</b> {esc(d['school_year'])}</p>
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

    def __init__(self, services, ctx, on_change=None):
        super().__init__()
        self.sv, self.ctx = services, ctx
        self.on_change = on_change
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
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
            self.student_id = None
            self.table.setRowCount(0)
            self.header.setText("Sélectionnez un élève.")
            self.totals.setText("")
            return
        try:
            page = self.sv.students.page(search=text, page=0, size=15)
        except Exception as e:
            self.student_id = None
            self.rows = []
            self.table.setRowCount(0)
            self.header.setText("Sélectionnez un élève.")
            self.totals.setText("")
            return handle_error(self, e)
        student_ids = set()
        for r in page.rows:
            student_ids.add(r["id"])
            it = QListWidgetItem(f"{r['last_name']} {r['first_name']} - {r['matricule']} - "
                                 f"{r['class_name'] or 'sans classe'}")
            it.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.results.addItem(it)
        if self.student_id not in student_ids:
            self.student_id = None
            self.rows = []
            self.table.setRowCount(0)
            self.header.setText("Sélectionnez un élève.")
            self.totals.setText("")

    def _pick(self, item):
        self.student_id = item.data(Qt.ItemDataRole.UserRole)
        self.load()

    def load(self):
        if self.student_id is None:
            return
        try:
            st = self.sv.payments.statement(
                self.student_id, self.sv.students.school_year)
        except Exception as e:
            self.table.setRowCount(0)
            self.header.setText("-")
            self.totals.setText("")
            return handle_error(self, e)
        s = st["student"]
        remise = f" - remise {s['tuition_discount']} %" if s["tuition_discount"] else ""
        self.header.setText(f"<b>{s['last_name']} {s['first_name']}</b> - {s['class_name']} - {s['school_year']}{remise}")
        self.rows = st["rows"]
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            cells = [r["label"], school.fmt_ar(r["due"]), school.fmt_ar(r["paid"]),
                     school.fmt_ar(r["balance"]), r["status"]]
            bg, fg = _status_colors(r["status"])
            for j, text in enumerate(cells):
                it = _item(text)
                it.setBackground(QBrush(QColor(bg)))
                it.setForeground(QBrush(QColor(fg)))
                self.table.setItem(i, j, it)
        self.totals.setText(f"Total dû : <b>{school.fmt_ar(st['total_due'])}</b> - payé : "
                            f"<b>{school.fmt_ar(st['total_paid'])}</b> - reste : "
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
                pid, receipt = self.sv.payments.record(
                    self.student_id, initial, self.sv.students.school_year)
                break
            except AppError as e:
                handle_error(self, e)
            except Exception as e:
                return handle_error(self, e)
        show_toast(self, f"Paiement enregistré - reçu {receipt}")
        self.load()
        if self.on_change is not None:
            self.on_change()
        if ask_confirmation(self, "Reçu", "Enregistrer le reçu en PDF ?"):
            try:
                save_receipt_pdf(self, self.sv, pid)
            except Exception as e:
                handle_error(self, e)

    def refresh(self):
        if self.search.text().strip():
            self._search()
        self.load()


class ArrearsTab(QWidget):
    def __init__(self, services, ctx):
        super().__init__()
        self.sv = services
        self.ctx = ctx
        years, classes = services.payments.arrears_filter_options()
        self.year_cb = QComboBox()
        self.year_cb.setObjectName("arrearsSchoolYearFilter")
        self.year_cb.addItem("Toutes les années", None)
        for year in years:
            self.year_cb.addItem(year, year)
        self.class_cb = QComboBox()
        self.class_cb.setObjectName("arrearsClassFilter")
        self.class_cb.addItem("Toutes les classes", None)
        for school_class in classes:
            self.class_cb.addItem(
                f"{school_class['name']} - {school_class['school_year']}", school_class["id"])
        self.month_cb = QComboBox()
        self.month_cb.setObjectName("arrearsMonthFilter")
        self.month_cb.addItem("Tous les mois échus", None)
        for month in school.SCHOOL_MONTHS:
            self.month_cb.addItem(school.MONTH_NAMES[month], month)
        self.compute_btn = QPushButton("Afficher les impayés")
        self.compute_btn.clicked.connect(self.compute)
        self.export_btn = QPushButton("Exporter CSV")
        self.export_btn.setObjectName("secondaryButton")
        self.export_btn.setEnabled(ctx.session.can("payments.export"))
        self.export_btn.clicked.connect(self.export_csv)
        top = QHBoxLayout()
        top.addWidget(QLabel("Année scolaire"))
        top.addWidget(self.year_cb)
        top.addWidget(QLabel("Classe"))
        top.addWidget(self.class_cb, 1)
        top.addWidget(QLabel("Mois d'écolage"))
        top.addWidget(self.month_cb)
        top.addWidget(self.compute_btn)
        top.addWidget(self.export_btn)
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "Matricule", "Nom", "Prénom", "Sexe", "Classe", "Année scolaire",
            "Poste impayé", "Mois", "Dû", "Payé", "Reste à payer"])
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.total = QLabel("Choisissez les filtres puis cliquez sur « Afficher les impayés ».")
        self.page_size = 100
        self.page = 0
        self.page_count = 1
        self.filters = None
        self.year_cb.currentIndexChanged.connect(self._year_changed)
        self.class_cb.currentIndexChanged.connect(self._filters_changed)
        self.month_cb.currentIndexChanged.connect(self._filters_changed)
        self.previous_btn = QPushButton("Précédent")
        self.previous_btn.setObjectName("arrearsPreviousPage")
        self.previous_btn.setEnabled(False)
        self.previous_btn.clicked.connect(self._previous_page)
        self.page_label = QLabel()
        self.next_btn = QPushButton("Suivant")
        self.next_btn.setObjectName("arrearsNextPage")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._next_page)
        pagination = QHBoxLayout()
        pagination.addWidget(self.total, 1)
        pagination.addWidget(self.previous_btn)
        pagination.addWidget(self.page_label)
        pagination.addWidget(self.next_btn)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.table, 1)
        lay.addLayout(pagination)

    def compute(self):
        self.filters = {
            "class_id": self.class_cb.currentData(),
            "school_year": self.year_cb.currentData(),
            "month": self.month_cb.currentData(),
        }
        self.page = 0
        self._load_page()

    def _year_changed(self):
        self._refresh_class_filter()
        self._filters_changed()

    def _filters_changed(self):
        if self.filters is not None:
            self.compute()

    def _refresh_class_filter(self):
        selected = self.class_cb.currentData()
        _years, classes = self.sv.payments.arrears_filter_options(
            self.year_cb.currentData())
        items = [("Toutes les classes", None)] + [
            (f"{item['name']} - {item['school_year']}", item["id"])
            for item in classes]
        self._set_class_filter(items, selected)

    def _set_class_filter(self, items, selected):
        _replace_combo_items(self.class_cb, items, selected)

    def refresh_filters(self):
        selected_year = self.year_cb.currentData()
        years, _classes = self.sv.payments.arrears_filter_options()
        year_items = [("Toutes les années", None)] + [(year, year) for year in years]
        self._selected_year = _replace_combo_items(
            self.year_cb, year_items, selected_year)
        selected_class = self.class_cb.currentData()
        _years, classes = self.sv.payments.arrears_filter_options(self._selected_year)
        class_items = [("Toutes les classes", None)] + [
            (f"{item['name']} - {item['school_year']}", item["id"])
            for item in classes]
        _replace_combo_items(self.class_cb, class_items, selected_class)
        if self.filters is not None:
            updated = {
                "class_id": self.class_cb.currentData(),
                "school_year": self.year_cb.currentData(),
                "month": self.month_cb.currentData(),
            }
            if updated != self.filters:
                self.page = 0
                self.filters = updated

    def refresh(self):
        if self.filters is not None:
            self._load_page()

    def _load_page(self):
        if self.filters is None:
            return
        try:
            result = self.sv.payments.arrears_page(
                **self.filters, page=self.page, size=self.page_size)
        except Exception as e:
            return handle_error(self, e)
        self.page = result["page"]
        self.page_count = result["pages"]
        page_rows = result["rows"]
        self.table.setRowCount(len(page_rows))
        for i, r in enumerate(page_rows):
            values = (
                r["matricule"], r["last_name"], r["first_name"], LABELS["gender"].get(r["gender"], ""),
                r["class_name"], r["school_year"], r["fee_label"],
                school.MONTH_NAMES.get(r["month"], "") if r["month"] else "-",
                school.fmt_ar(r["due"]), school.fmt_ar(r["paid"]), school.fmt_ar(r["balance"]),
            )
            for j, value in enumerate(values):
                v = value
                self.table.setItem(i, j, _item(v))
        self.total.setText(
            f"{result['students']} élève(s) - {result['total']} poste(s) impayé(s) - total restant : "
            f"<b>{school.fmt_ar(result['balance'])}</b>")
        self.page_label.setText(f"Page {self.page + 1} / {self.page_count}")
        self.previous_btn.setEnabled(self.page > 0)
        self.next_btn.setEnabled(self.page + 1 < self.page_count)

    def _previous_page(self):
        if self.page > 0:
            self.page -= 1
            self._load_page()

    def _next_page(self):
        if self.page + 1 < self.page_count:
            self.page += 1
            self._load_page()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter les impayés", "impayes.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            count = self.sv.payments.export_arrears_csv(
                path, class_id=self.class_cb.currentData(),
                school_year=self.year_cb.currentData(), month=self.month_cb.currentData())
            QMessageBox.information(self, "Export CSV", f"{count} poste(s) impayé(s) exporté(s).")
        except Exception as e:
            handle_error(self, e)


class FeesView(QWidget):
    def __init__(self, services, ctx, on_change=None):
        super().__init__()
        self.sv = services
        self.on_change = on_change
        self.tabs = QTabWidget()
        self.collect = CollectTab(services, ctx, on_change)
        self.arrears = ArrearsTab(services, ctx)
        self.tabs.addTab(self.collect, "Encaissement")
        self.tabs.addTab(self.arrears, "Impayés")

        pay_cols = [("class_name", "Classe"), ("school_year", "Année scolaire"),
                    ("receipt_no", "Reçu"), ("paid_at", "Date"), ("matricule", "Matricule"),
                    ("student_name", "Élève"), ("gender", "Genre", LABELS["gender"]),
                    ("fee_code", "Poste", school.FEE_ITEM_LABELS),
                    ("amount", "Montant (Ar)"),
                    ("method", "Mode", school.METHODS), ("payment_status", "État du paiement")]

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
                view.notify_changed()

        years, classes = services.payments.history_filter_options()
        self.history_year = QComboBox()
        self.history_year.setObjectName("historySchoolYearFilter")
        self.history_year.addItem("Toutes les années", None)
        for year in years:
            self.history_year.addItem(year, year)
        self.history_class = QComboBox()
        self.history_class.setObjectName("historyClassFilter")
        self.history_class.addItem("Toutes les classes", None)
        for school_class in classes:
            self.history_class.addItem(
                f"{school_class['name']} - {school_class['school_year']}", school_class["id"])
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Année scolaire"))
        filters.addWidget(self.history_year)
        filters.addSpacing(12)
        filters.addWidget(QLabel("Classe"))
        filters.addWidget(self.history_class)
        filters.addStretch(1)

        self.history = CrudView(services.payments, pay_cols, [], ctx, noun="paiement", read_only=True,
                                extra_actions=[("Reçu PDF", receipt, "payments.read"),
                                               ("Annuler le paiement", cancel, "payments.cancel")],
                                show_row_actions=False,
                                on_change=on_change,
                                page_loader=lambda search, sort, desc, page: services.payments.history_page(
                                    search, sort, desc, page, school_year=self.history_year.currentData(),
                                    class_id=self.history_class.currentData()))
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.addLayout(filters)
        history_layout.addWidget(self.history, 1)
        self.history_tab = history_tab
        self.history_year.currentIndexChanged.connect(self._history_filter_changed)
        self.history_class.currentIndexChanged.connect(self._history_filter_changed)
        self.tabs.addTab(history_tab, "Historique")
        if ctx.session.can("fees.read"):
            amount_fields = [
                ("droit_amount", "Droit"),
                ("photocopy_amount", "Photocopie"),
                ("uniform_amount", "Tenue"),
                ("activity_1_amount", "Calendrier"),
                ("activity_2_amount", "Classe verte"),
                ("activity_3_amount", "Enveloppe"),
                ("activity_4_amount", "Fête de fin d'année"),
                ("activity_5_amount", "Autre"),
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
            self.fees = CrudView(services.fees, cols, fields, ctx, noun="tarif",
                                 on_change=on_change)
            self.tabs.addTab(self.fees, "Tarifs par classe")
        self.tabs.currentChanged.connect(lambda _i: self._refresh_tab())
        lay = QVBoxLayout(self)
        lay.addWidget(self.tabs)

    def _refresh_tab(self):
        w = self.tabs.currentWidget()
        if w is self.history_tab:
            self.history.refresh()
        elif hasattr(w, "refresh"):
            w.refresh()

    def _history_filter_changed(self):
        selected = self.history_class.currentData()
        _years, classes = self.sv.payments.history_filter_options(
            self.history_year.currentData())
        items = [("Toutes les classes", None)] + [
            (f"{item['name']} - {item['school_year']}", item["id"])
            for item in classes]
        _replace_combo_items(self.history_class, items, selected)
        self.history.page_no = 0
        self.history.refresh()

    def refresh_filters(self):
        selected_year = self.history_year.currentData()
        years, _classes = self.sv.payments.history_filter_options()
        year_items = [("Toutes les années", None)] + [(year, year) for year in years]
        _replace_combo_items(self.history_year, year_items, selected_year)
        selected_class = self.history_class.currentData()
        _years, classes = self.sv.payments.history_filter_options(
            self.history_year.currentData())
        class_items = [("Toutes les classes", None)] + [
            (f"{item['name']} - {item['school_year']}", item["id"])
            for item in classes]
        _replace_combo_items(self.history_class, class_items, selected_class)
        self.arrears.refresh_filters()

    def refresh(self):
        self.collect.refresh()
        self.arrears.refresh()
        self.history.refresh()
        if hasattr(self, "fees"):
            self.fees.refresh()
