"""The bounded preflight scan enforces the same packed-frame domain as playback."""
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime


class TickScanTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(encoding='latin-1')
        self.lua.globals().root=Path(__file__).resolve().parents[1].as_posix()
        self.lua.execute("package.path=root..'/?.lua;'..package.path; ticks=require('code/tick-journal')")
        self.ticks=self.lua.globals().ticks

    def frame(self,tick=1,a=0,b=19999,c=19999,d=0):
        return struct.pack('<IHHIIHHII',tick,0,65535,a,b,65535,0,c,d).decode('latin-1')

    def test_chunk_continuity_and_empty_chunk(self):
        expected=1
        for count in (0,1,64,2340):
            data=''.join(self.frame(i) for i in range(expected,expected+count))
            self.assertEqual(self.ticks.scan(data,expected),expected+count)
            expected+=count

    def test_scan_and_decoder_reject_every_index_boundary(self):
        for index in range(4):
            for value in (20000,0xffffffff):
                values=[0]*4; values[index]=value
                data=self.frame(1,*values)
                with self.assertRaisesRegex(Exception,'RNG index'):self.ticks.scan(data,1)
                with self.assertRaisesRegex(Exception,'RNG index'):self.ticks.decode(data)

    def test_short_disordered_and_out_of_range_ticks_fail(self):
        for data,expected in ((self.frame()[:-1],1),(self.frame(2),1),
                              (self.frame()+self.frame(),1),
                              (self.frame(2147483647),2147483647)):
            with self.assertRaises(Exception):self.ticks.scan(data,expected)
        self.assertEqual(self.ticks.scan(self.frame(2147483646),2147483646),2147483647)


if __name__=='__main__':unittest.main()
