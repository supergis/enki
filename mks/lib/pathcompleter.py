"""
pathcompleter --- Path completer for Locator
============================================
"""


from PyQt4.QtCore import Qt
from PyQt4.QtGui import QApplication, QFileSystemModel, QPalette, QStyle

import os
import os.path
import glob

from mks.lib.htmldelegate import htmlEscape
from mks.core.locator import AbstractCompleter

import fnmatch
import re
regExPatterns = [fnmatch.translate(f) for f in ['*.pyc']]
compositeRegExpPattern = '(' + ')|('.join(regExPatterns) + ')'
filterRegExp = re.compile(compositeRegExpPattern)

def makeSuitableCompleter(text, pos):
    """Returns PathCompleter if text is normal path or GlobCompleter for glob
    """
    if '*' in text or '?' in text or '[' in text:
        return GlobCompleter(text)
    else:
        return PathCompleter(text, pos)

class AbstractPathCompleter(AbstractCompleter):
    """Base class for PathCompleter and GlobCompleter
    """
    
    # global object. Reused by all completers
    _fsModel = QFileSystemModel()

    _ERROR = 'error'
    _HEADER = 'currentDir'
    _STATUS = 'status'
    _DIRECTORY = 'directory'
    _FILE = 'file'
    
    def __init__(self, text):
        self._originalText = text
        self._dirs = []
        self._files = []
        self._error = None
        self._status = None
    
    @staticmethod
    def _filterHidden(paths):
        """Remove hidden and ignored files from the list
        """
        return [path for path in paths \
                    if not os.path.basename(path).startswith('.') and \
                        not filterRegExp.match(path)]

    def _classifyRowIndex(self, row):
        """Get list item type and index by it's row
        """

        if self._error:
            assert row == 0
            return (self._ERROR, 0)
        
        if row == 0:
            return (self._HEADER, 0)
        
        row -= 1
        if self._status:
            if row == 0:
                return (self._STATUS, 0)
            row -= 1
        
        if row in range(len(self._dirs)):
            return (self._DIRECTORY, row)
        row -= len(self._dirs)
        
        if row in range(len(self._files)):
            return (self._FILE, row)
        
        assert False

    def _formatHeader(self, text):
        """Format current directory for show it in the list of completions
        """
        return '<font style="background-color: %s; color: %s">%s</font>' % \
                (QApplication.instance().palette().color(QPalette.Window).name(),
                 QApplication.instance().palette().color(QPalette.WindowText).name(),
                 htmlEscape(text))

    def rowCount(self):
        """Row count in the list of completions
        """
        if self._error:
            return 1
        else:
            count = 1  # current directory
            if self._status:
                count += 1
            count += len(self._dirs)
            count += len(self._files)
            return count

    @staticmethod
    def _iconForPath(path):
        """Get icon for file or directory path. Uses QFileSystemModel
        """
        index = AbstractPathCompleter._fsModel.index(path)
        return AbstractPathCompleter._fsModel.data(index, Qt.DecorationRole)

    def text(self, row, column):
        """Item text in the list of completions
        """
        rowType, index = self._classifyRowIndex(row)
        if rowType == self._ERROR:
            return '<font color=red>%s</font>' % htmlEscape(self._error)
        elif rowType == self._HEADER:
            return self._formatHeader(self._headerText())
        elif rowType == self._STATUS:
            return '<i>%s</i>' % htmlEscape(self._status)
        elif rowType == self._DIRECTORY:
            return self._formatPath(self._dirs[index], True)
        elif rowType == self._FILE:
            return self._formatPath(self._files[index], False)

    def icon(self, row, column):
        """Item icon in the list of completions
        """
        rowType, index = self._classifyRowIndex(row)
        if rowType == self._ERROR:
            return QApplication.instance().style().standardIcon(QStyle.SP_MessageBoxCritical)
        elif rowType == self._HEADER:
            return None
        elif rowType == self._STATUS:
            return None
        elif rowType == self._DIRECTORY:
            return self._iconForPath(self._dirs[index])
        elif rowType == self._FILE:
            return self._iconForPath(self._files[index])

    def getFullText(self, row):
        """User clicked a row. Get inline completion for this row
        """
        row -= 1  # skip current directory
        path = None
        if row in range(len(self._dirs)):
            return self._dirs[row] + '/'
        else:
            row -= len(self._dirs)  # skip dirs
            if row in range(len(self._files)):
                return self._files[row]
        
        return None


class PathCompleter(AbstractPathCompleter):
    """Path completer for Locator. Supports globs
    
    Used by Open command
    """
    
    def __init__(self, text, pos):
        AbstractPathCompleter.__init__(self, text)
        
        enterredDir = os.path.dirname(text)
        enterredFile = os.path.basename(text)
        
        if enterredDir.startswith('/'):
            pass
        elif text.startswith('~'):
            enterredDir = os.path.expanduser(enterredDir)
        else:  # relative path
            enterredDir = os.path.abspath(os.path.join(os.path.curdir, enterredDir))
        
        self._path = os.path.normpath(enterredDir)
        if self._path != '/':
            self._path += '/'

        if not os.path.isdir(self._path):
            self._status = 'No directory %s' % self._path
            return

        try:
            filesAndDirs = os.listdir(self._path)
        except OSError, ex:
            self._error = unicode(str(ex), 'utf8')
            return
        
        if not filesAndDirs:
            self._status = 'Empty directory'
            return
            
        # filter matching
        variants = [path for path in filesAndDirs\
                        if path.startswith(enterredFile)]
        
        variants = self._filterHidden(variants)
        variants.sort()
        
        for variant in variants:
            absPath = os.path.join(self._path, variant)
            if os.path.isdir(absPath):
                self._dirs.append(absPath)
            else:
                self._files.append(absPath)

        if not self._dirs and not self._files:
            self._status = 'No matching files'

    def _headerText(self):
        """Get text, which shall be displayed on the header
        """
        return self._path
    
    def _formatPath(self, path, isDir):
        """Format file or directory for show it in the list of completions
        """
        path = os.path.basename(path)
        if isDir:
            path += '/'

        typedLen = self._lastTypedSegmentLength()
        inline = self.inline()
        typedLenPlusInline = typedLen + len(self.inline())
        return '<b>%s</b><u>%s</u>%s' % \
            (htmlEscape(path[:typedLen]),
             htmlEscape(path[typedLen:typedLenPlusInline]),
             htmlEscape(path[typedLenPlusInline:]))

    def _lastTypedSegmentLength(self):
        """Length of path segment, typed by a user
        
        For /home/a/Docu _lastTypedSegmentLength() is len("Docu")
        """
        return len(os.path.split(self._originalText)[1])
    
    def _commonStart(self, a, b):
        """The longest common start of 2 string
        """
        for index, char in enumerate(a):
            if len(b) <= index or b[index] != char:
                return a[:index]
        return a

    def inline(self):
        """Inline completion. Displayed after the cursor
        """
        if self._error is not None:
            return None
        else:
            if self._dirs or self._files:
                dirs = [os.path.basename(dir) + '/' for dir in self._dirs]
                files = [os.path.basename(file) for file in self._files]
                commonPart = reduce(self._commonStart, dirs + files)
                return commonPart[self._lastTypedSegmentLength():]
            else:
                return ''


class GlobCompleter(AbstractPathCompleter):
    """Path completer for Locator. Supports globs, does not support inline completion
    
    Used by Open command
    """
    def __init__(self, text):
        AbstractPathCompleter.__init__(self, text)
        variants = glob.iglob(os.path.expanduser(text) + '*')
        variants = self._filterHidden(variants)
        variants.sort()
        
        for path in sorted(variants):
            if os.path.isdir(path):
                self._dirs.append(path)
            else:
                self._files.append(path)
        
        if not self._dirs and not self._files:
            self._status = 'No matching files'

    def _formatPath(self, path, isDir):
        """GlobCompleter shows paths as is
        """
        return path

    def _headerText(self):
        """Get text, which shall be displayed on the header
        """
        return self._originalText
