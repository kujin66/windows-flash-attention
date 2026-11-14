"""Record native PE toolchain and loaded-module evidence in CUDA workers."""
import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path
import platform
import shutil
import struct
import sys


def pe_machine(path):
    with open(path, "rb") as stream:
        if stream.read(2) != b"MZ":
            raise RuntimeError(f"Not a PE image: {path}")
        stream.seek(60)
        offset, = struct.unpack("<I", stream.read(4))
        stream.seek(offset)
        if stream.read(4) != b"PE\0\0":
            raise RuntimeError(f"Invalid PE image: {path}")
        return struct.unpack("<H", stream.read(2))[0]


def expected_machine():
    return 0xAA64 if platform.machine().lower() in ("arm64", "aarch64") else 0x8664


def toolchain():
    expected = expected_machine()
    results = []
    for name in (sys.executable, sys._base_executable, "cl.exe", "link.exe", "nvcc.exe", "ptxas.exe"):
        path = shutil.which(name)
        if not path or pe_machine(path) != expected:
            raise RuntimeError(f"Native {platform.machine()} tool required: {name}: {path}")
        results.append(dict(path=path, machine=hex(expected),
                            sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest()))
    return results


def loaded_images():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    process = kernel.GetCurrentProcess()
    modules = (wintypes.HMODULE * 4096)()
    needed = wintypes.DWORD()
    if not psapi.EnumProcessModulesEx(process, modules, ctypes.sizeof(modules), ctypes.byref(needed), 3):
        raise ctypes.WinError(ctypes.get_last_error())
    if needed.value > ctypes.sizeof(modules):
        raise RuntimeError("Loaded-module evidence truncated")
    allowed = {expected_machine()}
    if 0xAA64 in allowed:
        allowed.update((0xA641, 0xA64E))  # Windows system ARM64EC / ARM64X images.
    result = []
    for module in modules[:needed.value // ctypes.sizeof(wintypes.HMODULE)]:
        name = ctypes.create_unicode_buffer(32768)
        if not psapi.GetModuleFileNameExW(process, module, name, len(name)):
            raise ctypes.WinError(ctypes.get_last_error())
        machine = pe_machine(name.value)
        if machine not in allowed or (name.value.lower().endswith(".pyd") and machine != expected_machine()):
            raise RuntimeError(f"Non-native loaded image: {name.value}: {machine:#x}")
        result.append(dict(path=name.value, machine=hex(machine)))
    return result
