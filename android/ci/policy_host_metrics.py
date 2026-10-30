"""Read current physical/commit headroom; resource values live in the policy."""
import ctypes
import os


def host_memory():
    if os.name != 'nt':
        raise RuntimeError('Pyfa local verification requires the actual Windows host metrics')
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),
                  *[(name,ctypes.c_ulonglong) for name in
                    ('total','available','commit_limit','commit_available',
                     'virtual_total','virtual_available','extended')]]
    status=Memory()
    status.length=ctypes.sizeof(status)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError(ctypes.get_last_error())
    return status.available,status.commit_available
