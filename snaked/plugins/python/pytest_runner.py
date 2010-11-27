import weakref

import glib
import pango
import gtksourceview2

from snaked.util import BuilderAware, join_to_file_dir

import pytest_launcher

class Escape(object): pass

class TestRunner(BuilderAware):
    """glade-file: pytest_runner.glade"""

    def __init__(self):
        super(TestRunner, self).__init__(join_to_file_dir(__file__, 'pytest_runner.glade'))

        self.buffer = gtksourceview2.Buffer()
        self.view = gtksourceview2.View()
        self.view.set_buffer(self.buffer)
        self.buffer_place.add(self.view)
        self.view.show()

        self.editor_ref = None
        self.timer_id = None
        self.test_proc = None
        self.collected_nodes = {}
        self.failed_nodes = {}
        self.hbox1.hide()
        self.escape = None

    def collect(self, conn):
        while conn.poll():
            msg = conn.recv()
            handler_name = 'handle_' + msg[0].lower()
            try:
                func = getattr(self, handler_name)
            except AttributeError:
                print 'TestRunner: %s not founded' % handler_name
            else:
                func(*msg[1:])

        return self.test_proc.is_alive()

    def run(self, editor, matches='', files=[]):
        self.editor_ref = weakref.ref(editor)

        self.tests.clear()
        self.collected_nodes.clear()
        self.failed_nodes.clear()
        self.tests_count = 0
        self.executed_tests = 0
        self.passed_tests_count = 0
        self.failed_tests_count = 0
        self.prevent_scroll = False
        self.buffer.delete(*self.buffer.get_bounds())
        self.progress.set_text('Running tests')

        proc, conn = pytest_launcher.run_test(editor.project_root, matches, files)
        self.test_proc = proc
        self.timer_id = glib.timeout_add(100, self.collect, conn)

    def show(self):
        self.editor_ref().popup_widget(self.hbox1)

    def hide(self, editor=None, *args):
        self.escape = None
        self.hbox1.hide()
        if editor:
            editor.view.grab_focus()

    def find_common_parent(self, nodes):
        if not nodes:
            return ''

        parent, _, _ = nodes[0].rpartition('::')
        while parent:
            if all(n.startswith(parent) for n in nodes):
                return parent

            parent, _, _ = parent.rpartition('::')

        return ''

    def handle_collected_tests(self, nodes):
        common_parent = self.find_common_parent(nodes)

        self.tests_count = len(nodes)
        self.progress_adj.set_upper(self.tests_count)

        def append(node, node_name):
            parent, sep, child = node_name.rpartition('::')
            if parent:
                if parent not in self.collected_nodes:
                    append(parent, parent)

                self.collected_nodes[node] = self.tests.append(
                    self.collected_nodes[parent], (child, pango.WEIGHT_NORMAL, node))
            else:
                self.collected_nodes[node] = self.tests.append(
                    None, (child, pango.WEIGHT_NORMAL, node))

        for node in nodes:
            node_name = node
            if common_parent:
                node_name = node[len(common_parent)+2:]
            append(node, node_name)

        if self.tests_count:
            self.tests_view.expand_all()
            nw = self.tests_view.size_request()[0]
            w = self.scrolledwindow1.get_size_request()[0]
            tw = self.hbox1.window.get_size()[0]
            if nw > w:
                if nw > tw/2: nw = tw/2
                self.scrolledwindow1.set_size_request(nw, -1)

    def handle_item_call(self, node):
        self.executed_tests += 1
        if self.executed_tests == 2:
            self.show()

        self.progress_adj.set_value(self.executed_tests)
        self.progress.set_text('Running test %d/%d' % (self.executed_tests, self.tests_count))

        self.tests.set(self.collected_nodes[node], 1, pango.WEIGHT_BOLD)

        if not self.prevent_scroll:
            path = self.tests.get_path(self.collected_nodes[node])
            self.tests_view.scroll_to_cell(path)

    def handle_pass(self, node):
        self.passed_tests_count += 1
        iter = self.collected_nodes[node]
        testname = self.tests.get_value(iter, 0)
        self.tests.set(iter, 0, u'\u2714 '.encode('utf8') + testname, 1, pango.WEIGHT_NORMAL)

    def handle_fail(self, node, msg):
        self.failed_tests_count += 1
        self.prevent_scroll = True
        self.failed_nodes[node] = msg
        iter = self.collected_nodes[node]
        testname = self.tests.get_value(iter, 0)
        self.tests.set(iter, 0, u'\u2716 '.encode('utf8') + testname, 1, pango.WEIGHT_BOLD)

        if self.failed_tests_count == 1:
            self.tests_view.set_cursor(self.tests.get_path(iter))
            self.show()
            self.tests_view.grab_focus()

    def handle_end(self):
        self.progress_adj.set_value(self.tests_count)
        self.progress.set_text('Done')

        if not self.tests_count:
            self.editor_ref().message('There are no any tests to run')

        if self.tests_count == self.passed_tests_count == 1:
            self.editor_ref().message('Test PASSED')

    def on_tests_view_cursor_changed(self, view):
        path, column = view.get_cursor()
        iter = self.tests.get_iter(path)
        node = self.tests.get_value(iter, 2)
        self.buffer.set_text(self.failed_nodes.get(node, ''))

    def on_popup(self):
        self.escape = Escape()
        self.editor_ref().push_escape(self.hide, self.escape)