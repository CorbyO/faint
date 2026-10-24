import gc
import os
import unittest
import weakref

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QObject, Signal, SignalInstance
from faint.qt_compat import install_compiled_signal_bridge


class SignalBridgeTests(unittest.TestCase):
    def test_arguments_and_receiver_lifetime(self):
        class Sender(QObject):
            changed = Signal(bool)

        calls = []
        class Receiver:
            def no_arguments(self):
                calls.append('method')

        original = SignalInstance.connect
        try:
            install_compiled_signal_bridge()
            sender = Sender()
            receiver = Receiver()
            sender.changed.connect(receiver.no_arguments)
            sender.changed.connect(lambda checked: calls.append(checked))
            sender.changed.emit(True)
            self.assertEqual(calls, ['method', True])
            reference = weakref.ref(receiver)
            del receiver
            gc.collect()
            self.assertIsNone(reference())
            sender.changed.emit(False)
            self.assertEqual(calls, ['method', True, False])
        finally:
            SignalInstance.connect = original
