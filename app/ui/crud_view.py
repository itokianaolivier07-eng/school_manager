from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget)

from app import config
from app.core.exceptions import AppError
from app.ui.forms import FormDialog
from app.ui.table_model import RowsModel
from app.ui.utils import handle_error


class CrudView(QWidget):
    def __init__(self, service, columns, fields, ctx, *, noun="élément", read_only=False,
                 extra_actions=()):
        super().__init__()
        self.service, self.columns, self.fields, self.ctx, self.noun = service, columns, fields, ctx, noun
        self.read_only = read_only
        self.sort_key, self.desc, self.page_no = None, service.default_desc, 0
        self.display_columns = list(columns) + [("_actions", "Actions")]
        self.model = RowsModel(self.display_columns)

        self.search = QLineEdit()
        self.search.setObjectName("searchField")
        self.search.setPlaceholderText("Rechercher…")
        self.search.setMaxLength(100)
        self.search.setClearButtonEnabled(True)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(config.SEARCH_DEBOUNCE_MS)
        self.timer.timeout.connect(self._search_changed)
        self.search.textChanged.connect(lambda _text: self.timer.start())

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(len(self.display_columns) - 1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(len(self.display_columns) - 1, 210)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_sort)
        self.table.doubleClicked.connect(lambda _i: self.view_item())

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.search, 1)
        s = ctx.session
        can_write = not read_only and s.can(service.write_perm)
        if can_write:
            b = QPushButton("＋ Ajouter")
            b.setObjectName("primaryButton")
            b.clicked.connect(self.add)
            top.addWidget(b)
        for label, callback, perm in extra_actions:
            if s.can(perm):
                b = QPushButton(label)
                b.setObjectName("secondaryButton")
                b.clicked.connect(lambda _checked=False, cb=callback: self._run(cb))
                top.addWidget(b)

        self.prev_btn, self.next_btn = QPushButton("Précédent"), QPushButton("Suivant")
        for button in (self.prev_btn, self.next_btn):
            button.setObjectName("secondaryButton")
            button.setMinimumWidth(88)
        self.prev_btn.clicked.connect(lambda: self._go(-1))
        self.next_btn.clicked.connect(lambda: self._go(1))
        self.info = QLabel()
        self.info.setObjectName("resultInfo")
        bottom = QHBoxLayout()
        bottom.addWidget(self.info, 1)
        bottom.addWidget(self.prev_btn)
        bottom.addWidget(self.next_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)
        layout.addLayout(bottom)

    def refresh(self):
        try:
            page = self.service.page(self.search.text(), self.sort_key, self.desc, self.page_no)
        except Exception as e:
            handle_error(self, e)
            return
        if self.page_no >= page.pages:
            self.page_no = page.pages - 1
            return self.refresh()
        self.model.set_rows(page.rows)
        self.info.setText(f"{page.total} résultat(s) — page {page.page + 1} / {page.pages}")
        self.prev_btn.setEnabled(page.page > 0)
        self.next_btn.setEnabled(page.page + 1 < page.pages)
        self._install_row_actions()

    def _install_row_actions(self):
        actions_col = len(self.display_columns) - 1
        s = self.ctx.session
        can_write = not self.read_only and s.can(self.service.write_perm)
        can_delete = not self.read_only and s.can(self.service.delete_perm)
        can_read = s.can(self.service.read_perm)
        for row_idx in range(self.model.rowCount()):
            cell = QWidget()
            cell.setObjectName("actionsCell")
            lay = QHBoxLayout(cell)
            lay.setContentsMargins(4, 2, 4, 2)
            lay.setSpacing(6)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if can_read:
                btn_view = QPushButton("Voir")
                btn_view.setObjectName("rowViewBtn")
                btn_view.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_view.setFixedHeight(28)
                btn_view.clicked.connect(lambda _=False, r=row_idx: self.view_item(r))
                lay.addWidget(btn_view)
            if can_write:
                btn_edit = QPushButton("Modifier")
                btn_edit.setObjectName("rowEditBtn")
                btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_edit.setFixedHeight(28)
                btn_edit.clicked.connect(lambda _=False, r=row_idx: self.edit(r))
                lay.addWidget(btn_edit)
            if can_delete:
                btn_del = QPushButton("Suppr.")
                btn_del.setObjectName("rowDeleteBtn")
                btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_del.setFixedHeight(28)
                btn_del.clicked.connect(lambda _=False, r=row_idx: self.remove(r))
                lay.addWidget(btn_del)
            self.table.setIndexWidget(self.model.index(row_idx, actions_col), cell)

    def _search_changed(self):
        self.page_no = 0
        self.refresh()

    def _go(self, delta):
        self.page_no = max(0, self.page_no + delta)
        self.refresh()

    def _on_sort(self, col):
        if col >= len(self.columns):
            return
        key = self.columns[col][0]
        if key not in self.service.repo.sort_fields:
            return
        self.desc = (not self.desc) if key == self.sort_key else False
        self.sort_key = key
        self.table.horizontalHeader().setSortIndicator(
            col, Qt.SortOrder.DescendingOrder if self.desc else Qt.SortOrder.AscendingOrder)
        self.page_no = 0
        self.refresh()

    def _row_id(self, row_idx=None):
        if row_idx is None:
            row_idx = self.table.currentIndex().row()
        row = self.model.row_at(row_idx)
        if row is None:
            QMessageBox.information(self, "Sélection", f"Sélectionnez d'abord un {self.noun}.")
            return None
        return row["id"]

    def _run(self, callback):
        try:
            callback(self)
        except Exception as e:
            handle_error(self, e)

    def _dialog(self, title, initial, submit, readonly=False):
        while True:
            dlg = FormDialog(title, self.fields, initial, self, readonly=readonly)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            if readonly:
                return
            values = dlg.values()
            try:
                submit(values)
                return
            except AppError as e:
                handle_error(self, e)
                initial = values
            except Exception as e:
                handle_error(self, e)
                return

    def add(self):
        self._dialog(f"Ajouter : {self.noun}", {}, self.service.create)
        self.refresh()

    def view_item(self, row_idx=None):
        id_ = self._row_id(row_idx)
        if id_ is None:
            return
        try:
            initial = self.service.get(id_)
        except Exception as e:
            return handle_error(self, e)
        self._dialog(f"Voir : {self.noun}", initial, lambda _v: None, readonly=True)

    def edit(self, row_idx=None):
        id_ = self._row_id(row_idx)
        if id_ is None or not self.ctx.session.can(self.service.write_perm):
            return
        try:
            initial = self.service.get(id_)
        except Exception as e:
            return handle_error(self, e)
        self._dialog(f"Modifier : {self.noun}", initial, lambda v: self.service.update(id_, v))
        self.refresh()

    def remove(self, row_idx=None):
        id_ = self._row_id(row_idx)
        if id_ is None:
            return
        if QMessageBox.question(self, "Confirmation", f"Supprimer définitivement ce {self.noun} ?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(id_)
        except Exception as e:
            handle_error(self, e)
        self.refresh()
