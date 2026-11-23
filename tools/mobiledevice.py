"""Minimal bridge to macOS's built-in MobileDevice framework.

Lets Python talk to a USB-connected iPhone using only what ships with macOS:
no Xcode, no Homebrew packages. CoreFoundation objects are converted to and
from Python values by round-tripping through binary property lists.
"""
import ctypes
import plistlib
from ctypes import POINTER, byref, c_char_p, c_int, c_long, c_uint, c_ulong, c_void_p

CF = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
MD = ctypes.CDLL("/System/Library/PrivateFrameworks/MobileDevice.framework/MobileDevice")

_UTF8 = 0x08000100
_BINARY_PLIST = 200

CF.CFStringCreateWithCString.restype = c_void_p
CF.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint]
CF.CFArrayGetCount.restype = c_long
CF.CFArrayGetCount.argtypes = [c_void_p]
CF.CFArrayGetValueAtIndex.restype = c_void_p
CF.CFArrayGetValueAtIndex.argtypes = [c_void_p, c_long]
CF.CFPropertyListCreateData.restype = c_void_p
CF.CFPropertyListCreateData.argtypes = [c_void_p, c_void_p, c_long, c_ulong, c_void_p]
CF.CFPropertyListCreateWithData.restype = c_void_p
CF.CFPropertyListCreateWithData.argtypes = [c_void_p, c_void_p, c_ulong, c_void_p, c_void_p]
CF.CFDataCreate.restype = c_void_p
CF.CFDataCreate.argtypes = [c_void_p, c_char_p, c_long]
CF.CFDataGetLength.restype = c_long
CF.CFDataGetLength.argtypes = [c_void_p]
CF.CFDataGetBytePtr.restype = c_void_p
CF.CFDataGetBytePtr.argtypes = [c_void_p]
CF.CFRelease.argtypes = [c_void_p]

MD.AMDCreateDeviceList.restype = c_void_p
for _name in (
    "AMDeviceConnect",
    "AMDeviceDisconnect",
    "AMDeviceIsPaired",
    "AMDeviceValidatePairing",
    "AMDevicePair",
    "AMDeviceStartSession",
    "AMDeviceStopSession",
    "AMDeviceGetInterfaceType",
):
    getattr(MD, _name).restype = c_int
    getattr(MD, _name).argtypes = [c_void_p]
MD.AMDeviceCopyValue.restype = c_void_p
MD.AMDeviceCopyValue.argtypes = [c_void_p, c_void_p, c_void_p]
MD.AMDeviceLookupApplications.restype = c_int
MD.AMDeviceLookupApplications.argtypes = [c_void_p, c_void_p, POINTER(c_void_p)]

USB = 1


def cfstr(text):
    return CF.CFStringCreateWithCString(None, text.encode(), _UTF8)


def to_python(cf_object):
    """Convert a CoreFoundation property-list object into a Python value."""
    if not cf_object:
        return None
    data = CF.CFPropertyListCreateData(None, cf_object, _BINARY_PLIST, 0, None)
    if not data:
        return None
    length = CF.CFDataGetLength(data)
    raw = ctypes.string_at(CF.CFDataGetBytePtr(data), length)
    CF.CFRelease(data)
    return plistlib.loads(raw)


def to_cf(value):
    """Convert a Python value into a CoreFoundation property-list object."""
    raw = plistlib.dumps(value, fmt=plistlib.FMT_BINARY)
    data = CF.CFDataCreate(None, raw, len(raw))
    result = CF.CFPropertyListCreateWithData(None, data, 0, None, None)
    CF.CFRelease(data)
    return result


def usb_devices():
    """Return handles for every device attached over USB."""
    array = MD.AMDCreateDeviceList()
    if not array:
        return []
    handles = [CF.CFArrayGetValueAtIndex(array, i) for i in range(CF.CFArrayGetCount(array))]
    return [h for h in handles if MD.AMDeviceGetInterfaceType(h) == USB]


class Device:
    """An open lockdown session with one device."""

    def __init__(self, handle):
        self.handle = handle

    def __enter__(self):
        code = MD.AMDeviceConnect(self.handle)
        if code != 0:
            raise RuntimeError(f"connect failed (0x{code & 0xFFFFFFFF:08x})")
        if not MD.AMDeviceIsPaired(self.handle):
            raise PermissionError("not paired")
        code = MD.AMDeviceValidatePairing(self.handle)
        if code != 0:
            raise PermissionError(f"pairing not valid (0x{code & 0xFFFFFFFF:08x})")
        code = MD.AMDeviceStartSession(self.handle)
        if code != 0:
            raise RuntimeError(f"session failed (0x{code & 0xFFFFFFFF:08x})")
        return self

    def __exit__(self, *exc):
        MD.AMDeviceStopSession(self.handle)
        MD.AMDeviceDisconnect(self.handle)

    def value(self, key=None, domain=None):
        """Read a lockdown value, or a whole domain when key is None."""
        cf_domain = cfstr(domain) if domain else None
        cf_key = cfstr(key) if key else None
        return to_python(MD.AMDeviceCopyValue(self.handle, cf_domain, cf_key))

    def apps(self, attributes, app_type="User"):
        """Look up installed apps, returning the requested attributes for each."""
        options = to_cf({"ApplicationType": app_type, "ReturnAttributes": list(attributes)})
        out = c_void_p()
        code = MD.AMDeviceLookupApplications(self.handle, options, byref(out))
        if code != 0:
            raise RuntimeError(f"app lookup failed (0x{code & 0xFFFFFFFF:08x})")
        return to_python(out.value) or {}


# --- File access (AFC) -------------------------------------------------------
# AFC exposes the phone's media area: camera roll files, the Photos database,
# music, books, recordings and downloads. It cannot see inside other apps.

MD.AMDeviceSecureStartService.restype = c_int
MD.AMDeviceSecureStartService.argtypes = [c_void_p, c_void_p, c_void_p, POINTER(c_void_p)]
MD.AMDServiceConnectionGetSocket.restype = c_int
MD.AMDServiceConnectionGetSocket.argtypes = [c_void_p]
MD.AMDServiceConnectionGetSecureIOContext.restype = c_void_p
MD.AMDServiceConnectionGetSecureIOContext.argtypes = [c_void_p]
MD.AFCConnectionOpen.restype = c_int
MD.AFCConnectionOpen.argtypes = [c_int, c_uint, POINTER(c_void_p)]
MD.AFCConnectionSetSecureContext.restype = None
MD.AFCConnectionSetSecureContext.argtypes = [c_void_p, c_void_p]
MD.AFCConnectionClose.restype = c_int
MD.AFCConnectionClose.argtypes = [c_void_p]
MD.AFCDirectoryOpen.restype = c_int
MD.AFCDirectoryOpen.argtypes = [c_void_p, c_char_p, POINTER(c_void_p)]
MD.AFCDirectoryRead.restype = c_int
MD.AFCDirectoryRead.argtypes = [c_void_p, c_void_p, POINTER(c_char_p)]
MD.AFCDirectoryClose.restype = c_int
MD.AFCDirectoryClose.argtypes = [c_void_p, c_void_p]
MD.AFCFileInfoOpen.restype = c_int
MD.AFCFileInfoOpen.argtypes = [c_void_p, c_char_p, POINTER(c_void_p)]
MD.AFCDeviceInfoOpen.restype = c_int
MD.AFCDeviceInfoOpen.argtypes = [c_void_p, POINTER(c_void_p)]
MD.AFCKeyValueRead.restype = c_int
MD.AFCKeyValueRead.argtypes = [c_void_p, POINTER(c_char_p), POINTER(c_char_p)]
MD.AFCKeyValueClose.restype = c_int
MD.AFCKeyValueClose.argtypes = [c_void_p]


class Files:
    """Read-only view of the phone's media area."""

    def __init__(self, device):
        service = c_void_p()
        code = MD.AMDeviceSecureStartService(device.handle, cfstr("com.apple.afc"), None, byref(service))
        if code != 0:
            raise RuntimeError(f"file service failed (0x{code & 0xFFFFFFFF:08x})")
        self._conn = c_void_p()
        code = MD.AFCConnectionOpen(MD.AMDServiceConnectionGetSocket(service), 0, byref(self._conn))
        if code != 0:
            raise RuntimeError(f"file connection failed (0x{code & 0xFFFFFFFF:08x})")
        secure = MD.AMDServiceConnectionGetSecureIOContext(service)
        if secure:
            MD.AFCConnectionSetSecureContext(self._conn, secure)

    def _read_pairs(self, handle):
        pairs = {}
        key, value = c_char_p(), c_char_p()
        while MD.AFCKeyValueRead(handle, byref(key), byref(value)) == 0 and key.value:
            pairs[key.value.decode()] = (value.value or b"").decode()
        MD.AFCKeyValueClose(handle)
        return pairs

    def volume(self):
        """Filesystem totals reported by the phone."""
        handle = c_void_p()
        if MD.AFCDeviceInfoOpen(self._conn, byref(handle)) != 0:
            return {}
        return self._read_pairs(handle)

    def info(self, path):
        """Return file metadata (size, type, modified time) or None."""
        handle = c_void_p()
        if MD.AFCFileInfoOpen(self._conn, path.encode(), byref(handle)) != 0:
            return None
        return self._read_pairs(handle)

    def listdir(self, path):
        """Return the names inside a directory."""
        handle = c_void_p()
        if MD.AFCDirectoryOpen(self._conn, path.encode(), byref(handle)) != 0:
            return []
        names = []
        entry = c_char_p()
        while MD.AFCDirectoryRead(self._conn, handle, byref(entry)) == 0 and entry.value:
            name = entry.value.decode(errors="replace")
            if name not in (".", ".."):
                names.append(name)
        MD.AFCDirectoryClose(self._conn, handle)
        return names
