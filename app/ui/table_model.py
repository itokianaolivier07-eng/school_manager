from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class RowsModel(QAbstractTableModel):
    """Modèle léger : ne contient que la page courante (100 lignes), pas les 30 000."""

    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.columns = columns   # [(clé, titre, {valeur: libellé} optionnel)]
        self.rows = []

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def row_at(self, i):
        return self.rows[i] if 0 <= i < len(self.rows) else None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        col = self.columns[index.column()]
        value = self.rows[index.row()][col[0]]
        if len(col) > 2 and col[2]:
            value = col[2].get(value, value)
        return "" if value is None else str(value)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columns[section][1]
        return None
