from __future__ import division, absolute_import, unicode_literals

from qtpy import QtCore
from qtpy import QtWidgets
from qtpy.QtCore import Qt

from . import core
from . import gitcmds
from . import hotkeys
from . import icons
from . import qtutils
from . import utils
from .i18n import N_
from .interaction import Interaction
from .models import main
from .models import selection
from .widgets import completion
from .widgets import defs
from .widgets import filetree


def run():
    files = selection.selected_group()
    if not files:
        return
    s = selection.selection()
    model = main.model()
    launch_with_head(files, bool(s.staged), model.head)


def launch_with_head(filenames, staged, head):
    if head == 'HEAD':
        left = None
    else:
        left = head
    launch(left=left, staged=staged, paths=filenames)


def launch(left=None, right=None, paths=None,
           left_take_parent=False, staged=False):
    """Launches 'git difftool' with given parameters"""

    difftool_args = ['git', 'difftool', '--no-prompt']
    if staged:
        difftool_args.append('--cached')

    if left:
        if left_take_parent:
            # Check root commit (no parents and thus cannot execute '~')
            model = main.model()
            git = model.git
            status, out, err = git.rev_list(left, parents=True, n=1)
            Interaction.log_status(status, out, err)
            if status:
                raise OSError('git rev-list command failed')

            if len(out.split()) >= 2:
                # Commit has a parent, so we can take its child as requested
                left += '~'
            else:
                # No parent, assume it's the root commit, so we have to diff
                # against the empty tree.  The empty tree is a built-in
                # git constant SHA1.  The empty tree is a built-in Git SHA1.
                left = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
        difftool_args.append(left)

    if right:
        difftool_args.append(right)

    if paths:
        difftool_args.append('--')
        difftool_args.extend(paths)

    core.fork(difftool_args)


def diff_commits(parent, a, b):
    dlg = FileDiffDialog(parent, a=a, b=b)
    dlg.show()
    dlg.raise_()
    return dlg.exec_() == QtWidgets.QDialog.Accepted


def diff_expression(parent, expr,
                    create_widget=False, hide_expr=False):
    dlg = FileDiffDialog(parent, expr=expr, hide_expr=hide_expr)
    if create_widget:
        return dlg
    dlg.show()
    dlg.raise_()
    return dlg.exec_() == QtWidgets.QDialog.Accepted


class FileDiffDialog(QtWidgets.QDialog):

    def __init__(self, parent, a=None, b=None, expr=None, title=None,
                 hide_expr=False):
        QtWidgets.QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_MacMetalStyle)

        self.a = a
        self.b = b
        self.diff_expr = expr

        if title is None:
            title = N_('git-cola diff')

        self.setWindowTitle(title)
        self.setWindowModality(QtCore.Qt.WindowModal)

        self.expr = completion.GitRefLineEdit(parent=self)
        if expr is not None:
            self.expr.setText(expr)

        if expr is None or hide_expr:
            self.expr.hide()

        self.tree = filetree.FileTree(parent=self)

        self.diff_button = qtutils.create_button(text=N_('Compare'),
                                                 icon=icons.diff(),
                                                 enabled=False)
        self.close_button = qtutils.close_button()

        self.button_layout = qtutils.hbox(defs.no_margin, defs.spacing,
                                          qtutils.STRETCH,
                                          self.diff_button, self.close_button)

        self.main_layout = qtutils.vbox(defs.margin, defs.spacing,
                                        self.expr, self.tree,
                                        self.button_layout)
        self.setLayout(self.main_layout)

        self.tree.itemSelectionChanged.connect(self.tree_selection_changed)
        self.tree.itemDoubleClicked.connect(self.tree_double_clicked)
        self.tree.up.connect(self.focus_input)

        self.expr.textChanged.connect(self.text_changed)

        self.expr.activated.connect(self.focus_tree)
        self.expr.down.connect(self.focus_tree)
        self.expr.enter.connect(self.focus_tree)

        qtutils.connect_button(self.diff_button, self.diff)
        qtutils.connect_button(self.close_button, self.close)

        qtutils.add_action(self, 'Focus Input', self.focus_input, hotkeys.FOCUS)
        qtutils.add_close_action(self)

        self.resize(720, 420)
        self.refresh()

    def focus_tree(self):
        self.tree.setFocus()

    def focus_input(self):
        self.expr.setFocus()

    def text_changed(self, txt):
        self.diff_expr = txt
        self.refresh()

    def refresh(self):
        if self.diff_expr is not None:
            self.diff_arg = utils.shell_split(self.diff_expr)
        elif self.b is None:
            self.diff_arg = [self.a]
        else:
            self.diff_arg = [self.a, self.b]
        self.refresh_filenames()

    def refresh_filenames(self):
        if self.a and self.b is None:
            filenames = gitcmds.diff_index_filenames(self.a)
        else:
            filenames = gitcmds.diff(self.diff_arg)
        self.tree.set_filenames(filenames, select=True)

    def tree_selection_changed(self):
        self.diff_button.setEnabled(self.tree.has_selection())

    def tree_double_clicked(self, item, column):
        path = self.tree.filename_from_item(item)
        left, right = self._left_right_args()
        launch(left=left, right=right, paths=[path])

    def diff(self):
        paths = self.tree.selected_filenames()
        left, right = self._left_right_args()
        launch(left=left, right=right, paths=paths)

    def _left_right_args(self):
        if self.diff_arg:
            left = self.diff_arg[0]
        else:
            left = None
        if len(self.diff_arg) > 1:
            right = self.diff_arg[1]
        else:
            right = None
        return (left, right)
