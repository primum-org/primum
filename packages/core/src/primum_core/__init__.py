"""Primum core: the pure library shared by the runtime, the desktop app and the backend.

It holds the project model, validation, the compiler and the simulator. It must never
touch hardware, the network, storage or the system clock: those enter as parameters.
"""

__version__ = "0.0.1"
