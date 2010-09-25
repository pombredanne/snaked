import gtk
import gtksourceview2

from gsignals import connect_all

from .signals import EditorSignals

class Editor(object):
    """
    The main editor window.
    
    Editor can be both standalone window and embedded into tab. 
    """
    
    def __init__(self):    
        self.signals = EditorSignals()
        
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect('delete-event', self.on_delete_event)
        self.window.connect('destroy', self.on_destroy)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.window.add(scrolled_window)
                
        self.buffer = gtksourceview2.Buffer()
        self.view = gtksourceview2.View()
        
        self.view.props.buffer = self.buffer
        
        scrolled_window.add(self.view)

        self.window.show_all()

    def load_file(self, filename):
        self.uri = filename
        
        self.buffer.set_text(open(filename).read().decode('utf-8'))
        self.buffer.place_cursor(self.buffer.get_start_iter())
        
        self.window.set_title(filename)
        
    def on_destroy(self, *args):
        self.signals.editor_closed.emit(self)
    
    def on_delete_event(self, *args):
        return False
    
    def close(self):
        del self.window

        
class EditorManager(object):
    """
    Keeps window editor list
    """
    
    def __init__(self):
        self.editors = []
        self.style_manager = gtksourceview2.style_scheme_manager_get_default()
        self.lang_manager = gtksourceview2.language_manager_get_default()
        
    def open(self, filename):
        editor = Editor()
        self.editors.append(editor)
        connect_all(self, editor.signals)
        
        self.set_editor_lang(editor, filename)
        self.set_editor_style(editor)
        
        if filename:
            editor.load_file(filename)
        
        return editor
    
    def set_editor_lang(self, editor, filename):
        lang = self.lang_manager.guess_language(filename, None)
        editor.buffer.set_language(lang)
        
    def set_editor_style(self, editor):
        style_scheme = self.style_manager.get_scheme('babymate')
        editor.buffer.set_style_scheme(style_scheme)
    
    @EditorSignals.editor_closed(idle=True)
    def on_editor_closed(self, sender, editor):
        self.editors.remove(editor)
        if not self.editors:
            gtk.main_quit()
