"""The one background-thread pattern: a daemon thread, results back on the main thread.

Qt only lets the main thread touch widgets, so slow work runs on a plain
'threading.Thread' and the result comes back through a Qt signal, which is safe to
emit from any thread. The app uses no 'QThread' anywhere. 'QThread' only pays for
itself when a worker object has to live in the other thread and keep answering calls
there, and every worker here just runs one function and reports once.
"""

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal


class _MainThreadDispatcher(QObject):
    """Runs a function on the main thread on behalf of a worker thread.

    A Qt signal is the only safe way to reach the main thread from a worker thread,
    and only a QObject can declare one. Qt also decides where to run a slot by
    looking at the receiving object's thread, so this has to be an object that
    belongs to the main thread.
    """

    invoked = Signal(object)  # carries a function that takes no arguments

    def __init__(self) -> None:
        super().__init__()
        self.invoked.connect(self._on_invoked)

    def _on_invoked(self, call: Callable[[], None]) -> None:
        """Call the emitted function. Qt runs this on the main thread."""
        call()


# One instance for the whole program, built at import time, which always happens on
# the main thread. A short lived instance per call would be unsafe. It could be
# garbage collected while its signal was still in flight, and Qt drops a pending
# signal whose receiver is gone, so the callback would silently never run.
_dispatcher = _MainThreadDispatcher()


def run_in_thread[T](
    fn: Callable[[], T],
    *,
    on_success: Callable[[T], None],
    on_error: Callable[[Exception], None],
) -> None:
    """Run 'fn' on a daemon thread and report back on the main thread.

    Exactly one of 'on_success' or 'on_error' runs, always on the main thread, so
    both are free to touch widgets.

    'fn' takes no arguments, so bind whatever it needs in a closure at the call site.
    Read the values you need off the widgets before starting, because 'fn' itself
    must never touch a widget, a pixmap, or any other Qt object.

    Nothing is returned. A caller that needs to know whether its job is still running
    keeps its own flag, which is cheaper than holding a thread it never joins.
    """

    def body() -> None:
        try:
            result = fn()
        except Exception as exc:
            # Copy the error into a name of our own. Python deletes 'exc' the moment
            # this block ends, and the function emitted below runs later on the main
            # thread, by which time 'exc' would be gone.
            error = exc
            _dispatcher.invoked.emit(lambda: on_error(error))
        else:
            _dispatcher.invoked.emit(lambda: on_success(result))

    threading.Thread(target=body, daemon=True).start()