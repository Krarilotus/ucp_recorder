"""Real Win32 conversion on private buffers; never attaches to a game process."""
import ctypes
import os
from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Win32 codepage conversion requires Windows')
class NativeEncodingTests(unittest.TestCase):
    def test_actual_codepages_reject_loss_and_preserve_multibyte_strings(self):
        memory = ctypes.create_string_buffer(30000)
        base = 0x100000
        def pointer(address, size=1):
            if address == 0:
                return None
            self.assertTrue(base <= address and address + size <= base + len(memory))
            return ctypes.addressof(memory) + address - base
        def read(address, size):
            return ctypes.string_at(pointer(address, size), size)
        def write(address, data):
            ctypes.memmove(pointer(address, len(data)), data, len(data))
        api = ctypes.WinDLL('kernel32.dll')
        ptr, integer = ctypes.c_void_p, ctypes.c_int
        api.MultiByteToWideChar.argtypes = [integer, integer, ptr, integer, ptr, integer]
        api.WideCharToMultiByte.argtypes = [integer, integer, ptr, integer, ptr, integer, ptr, ptr]
        def bind(library, name, count):
            self.assertEqual(library, b'kernel32.dll')
            name = name.decode()
            self.assertEqual(count, 6 if name == 'MultiByteToWideChar' else 8)
            def call(page, flags, source, length, target, capacity, *rest):
                if name == 'MultiByteToWideChar':
                    return api.MultiByteToWideChar(page, flags, pointer(source, length), length,
                                                   pointer(target, capacity*2), capacity)
                default, used = rest
                return api.WideCharToMultiByte(page, flags, pointer(source, length*2), length,
                                               pointer(target, capacity), capacity, pointer(default), pointer(used, 4))
            return call
        lua = LuaRuntime(encoding=None, unpack_returned_tuples=True)
        g = lua.globals()
        g.source_root = ROOT.as_posix().encode()
        g.bind = bind
        g.allocate = lambda size, zero: base if size <= len(memory) and zero else self.fail('Buffer overrun')
        g.write = write; g.read = read
        g.read_int = lambda address: int.from_bytes(read(address,4), 'little')
        g.write_int = lambda address, value: write(address, int(value).to_bytes(4, 'little'))
        lua.execute(b'''
package.path=source_root..'/?.lua;'..package.path
core={allocate=allocate,writeString=write,readString=read,readInteger=read_int,writeInteger=write_int}
package.loaded['code/platform']={stdcall=bind}
encode=require('code/text-encoding').encode
''')
        samples = {1252:'Zurück Français Español Italiano',1250:'Łódź árvíztűrő',
                   1251:'Повтор',1254:'İğüşçöı',936:'观看回放',1256:'بازپخش بازیکن',65001:'中文 فارسی'}
        for page,text in samples.items():
            with self.subTest(page=page):
                expected = text.replace('\u06cc','\u064a') if page == 1256 else text
                codec = 'utf-8' if page == 65001 else f'cp{page}'
                self.assertEqual(g.encode(text.encode(),page),expected.encode(codec))
        self.assertIsNone(g.encode('中文'.encode(),1252))
        self.assertIsNone(g.encode('Ő'.encode(),1252))  # must not silently become O
        self.assertIsNone(g.encode(b'bad\xff',1251))
        self.assertIsNone(g.encode('é'.encode(),99999))
        self.assertIsNone(g.encode(('é'*4096).encode(),1252))
        self.assertEqual(g.encode(b'Player %d',1252),b'Player %d')
        catalogs = lua.eval(b"require('code/locale').translations")
        pages = {'de':1252,'fr':1252,'ru':1251,'hu':1250,'tr':1254,
                 'zh':936,'es':1252,'fa':1256,'it':1252,'pl':1250}
        for language,page in pages.items():
            for key,value in catalogs[language.encode()].items():
                with self.subTest(language=language, key=key.decode()):
                    text = value.decode()
                    if page == 1256:
                        text = text.replace('\u06cc','\u064a')
                    self.assertEqual(g.encode(value,page),text.encode(f'cp{page}'))
