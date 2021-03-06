"""
searchresultsdock --- Search results dock widget
================================================

Shows results with SearchResultsModel
"""

from PyQt4.QtCore import Qt, pyqtSignal, QModelIndex
from PyQt4.QtGui import QFontMetrics, QHBoxLayout, QIcon, \
                        QTreeView, QWidget, QPushButton
from enki.widgets.dockwidget import DockWidget
from enki.core.core import core
from enki.lib.htmldelegate import HTMLDelegate

import searchresultsmodel


class ExpandCollapseAllButton(QPushButton):
    """Expand all/Collapse all button and functionality
    """
    def __init__(self, toolBar, view, model):
        QPushButton.__init__(self, QIcon(':enkiicons/scope.png'), "Ex&pand all", toolBar)
        self._action = toolBar.insertWidget(toolBar.actions()[0], self)
        self.setMinimumWidth(QFontMetrics(self.font()).width("Colla&pse all)") + 36)
        self.setStyleSheet("padding: 0")
        self.setFlat(True)
        self._view = view
        self._model = model
        self.clicked.connect(self._onTriggered)
        self._view.expanded.connect(self._update)
        self._view.collapsed.connect(self._update)
        self._model.rowsInserted.connect(self._update)
        self._model.rowsRemoved.connect(self._update)
        self._update()

    def _update(self):
        """Update action text according to expanded state of the first item
        """
        if self._model.empty():
            self._action.setEnabled(False)
        else:
            self._action.setEnabled(True)
            if self._isFirstFileExpanded():
                self.setText("Colla&pse all")
            else:
                self.setText("Ex&pand all")

    def _onTriggered(self):
        """Expand or colapse all search results
        """
        self._view.expanded.disconnect(self._update)
        self._view.collapsed.disconnect(self._update)

        if self._isFirstFileExpanded():
            self._view.collapseAll()
        else:
            self._view.expandAll()
        self._update()
        self._view.setFocus()

        self._view.expanded.connect(self._update)
        self._view.collapsed.connect(self._update)

    def _isFirstFileExpanded(self):
        """Check if first file in the search results is expanded
        """
        return self._view.isExpanded(self._model.index(0, 0, QModelIndex()))


class CheckUncheckAllButton(QPushButton):
    """Check/Uncheck all matches button for replace mode
    """
    def __init__(self, toolBar, view, model):
        QPushButton.__init__(self, QIcon(':enkiicons/button-ok.png'), "Unc&heck all", toolBar)
        self._action = toolBar.insertWidget(toolBar.actions()[0], self)
        self.setMinimumWidth(QFontMetrics(self.font()).width("Uncheck all)") + 36)
        self.setStyleSheet("padding: 0")
        self.setFlat(True)
        self._view = view
        self._model = model
        self.clicked.connect(self._onTriggered)
        self._model.dataChanged.connect(self._update)
        self._model.rowsInserted.connect(self._update)
        self._model.rowsRemoved.connect(self._update)
        self._update()

    def _update(self):
        """Update action text according to expanded state of the first item
        """
        if self._model.empty():
            self._action.setEnabled(False)
        else:
            self._action.setEnabled(True)
            if self._model.isFirstMatchChecked():
                self.setText("Unc&heck all")
            else:
                self.setText("C&heck all")

    def _onTriggered(self):
        """Expand or colapse all search results
        """
        self._model.dataChanged.disconnect(self._update)
        if self._model.isFirstMatchChecked():
            self._model.setCheckStateForAll(Qt.Unchecked)
        else:
            self._model.setCheckStateForAll(Qt.Checked)
        self._update()
        self._view.setFocus()
        self._model.dataChanged.connect(self._update)

    def show(self):
        """Show on tool bar
        """
        self._action.setVisible(True)

    def hide(self):
        """Hide on tool bar
        """
        self._action.setVisible(False)


class SearchResultsDock(DockWidget):
    """Dock with search results
    """

    onResultsHandledByReplaceThread = pyqtSignal(str, list)

    def __init__(self, parent):
        DockWidget.__init__( self, parent, "&Search Results", QIcon(":/enkiicons/search.png"), "Alt+S")

        # actions
        widget = QWidget( self )

        self._model = searchresultsmodel.SearchResultsModel(self)
        self.onResultsHandledByReplaceThread.connect(self._model.onResultsHandledByReplaceThread)

        self._view = QTreeView( self )
        self._view.setHeaderHidden( True )
        self._view.setUniformRowHeights( True )
        self._view.setModel( self._model )
        self._delegate = HTMLDelegate()
        self._view.setItemDelegate(self._delegate)

        self._layout = QHBoxLayout( widget )
        self._layout.setMargin( 5 )
        self._layout.setSpacing( 5 )
        self._layout.addWidget( self._view )

        self.setWidget( widget )
        self.setFocusProxy(self._view)

        # connections
        self._model.firstResultsAvailable.connect(self.show)
        self._view.activated.connect(self._onResultActivated)

        core.actionManager().addAction("mView/aSearchResults", self.showAction())

        self._expandCollapseAll = ExpandCollapseAllButton(self.titleBarWidget(), self._view, self._model)
        self._checkUncheckAll = None

    def del_(self):
        core.actionManager().removeAction("mView/aSearchResults")

    def _onResultActivated(self, index ):
        """Item doubleclicked in the model, opening file
        """
        result = index.internalPointer()
        if isinstance(result, searchresultsmodel.Result):
            fileResults = index.parent().internalPointer()
            core.workspace().goTo( result.fileName,
                                   line=result.line,
                                   column=result.column,
                                   selectionLength=len(result.match.group(0)))
            core.mainWindow().statusBar().showMessage('Match %d of %d' % \
                                                      (fileResults.results.index(result) + 1,
                                                       len(fileResults.results)), 3000)
            self.setFocus()

    def clear(self):
        """Clear themselves
        """
        self._model.clear()

    def appendResults(self, fileResultList):
        """Append results. Handler for signal from the search thread
        """
        self._model.appendResults(fileResultList)

    def getCheckedItems(self):
        """Get items, which must be replaced, as dictionary {file name : list of items}
        """
        items = {}

        for fileRes in self._model.fileResults:
            for row, result in enumerate(fileRes.results):
                if result.checkState == Qt.Checked :
                    if not result.fileName in items:
                        items[result.fileName] = []
                    items[ result.fileName ].append(result)
        return items

    def setReplaceMode(self, enabled):
        """When replace mode is enabled, dock shows checkbox near every item
        """
        self._model.setReplaceMode(enabled)
        if enabled:
            if self._checkUncheckAll is None:
                self._checkUncheckAll = CheckUncheckAllButton(self.titleBarWidget(), self._view, self._model)
            self._checkUncheckAll.show()
        else:
            if self._checkUncheckAll is not None:
                self._checkUncheckAll.hide()

    def matchesCount(self):
        """Get count of matches, stored by the model
        """
        return self._model.matchesCount()
