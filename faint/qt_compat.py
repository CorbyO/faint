"""Signal bridge for distribution PySide builds using CPython's full C API."""


def install_compiled_signal_bridge():
    import weakref

    from PySide6.QtCore import SignalInstance

    if getattr(SignalInstance.connect, "_faint_bridge", False):
        return
    namespace = {"original_connect": SignalInstance.connect, "weakref": weakref}
    # These functions must be real CPython functions. Full-API Shiboken builds
    # inspect Python function/weakref internals that compiled functions lack.
    exec(
        """
def connect(self, callback, *options, **kwargs):
    function = getattr(callback, '__func__', callback)
    code = getattr(function, '__code__', None)
    if code is not None:
        receiver = getattr(callback, '__self__', None)
        limit = None if code.co_flags & 4 else max(0, code.co_argcount - (receiver is not None))
        if receiver is not None:
            reference = weakref.ref(receiver)
            def bridge(*args):
                target = reference()
                if target is not None:
                    return function(target, *(args if limit is None else args[:limit]))
        else:
            def bridge(*args):
                return function(*(args if limit is None else args[:limit]))
        callback = bridge
    return original_connect(self, callback, *options, **kwargs)
connect._faint_bridge = True
""",
        namespace,
    )
    SignalInstance.connect = namespace["connect"]
