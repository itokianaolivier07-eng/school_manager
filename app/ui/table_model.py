from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class RowsModel(QAbstractTableModel):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.rows = []

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = [dict(r) if hasattr(r, "keys") else r for r in rows]
        self.endResetModel()

    def row_at(self, i):
        return self.rows[i] if 0 <= i < len(self.rows) else None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        col = self.columns[index.column()]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            alignment = (Qt.AlignmentFlag.AlignCenter if col[0] == "_actions"
                         else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return alignment
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        key = col[0]
        if key == "_actions":
            return ""
        row = self.rows[index.row()]
        value = row.get(key) if isinstance(row, dict) else row[key]
        if len(col) > 2 and col[2]:
            value = col[2].get(value, value)
        return "" if value is None else str(value)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.TextAlignmentRole:
            alignment = (Qt.AlignmentFlag.AlignCenter if self.columns[section][0] == "_actions"
                         else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return alignment
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columns[section][1]
        return None
