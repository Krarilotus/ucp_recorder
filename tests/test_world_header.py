"""Header references are checked in full before any captured data is read."""
import hashlib
from pathlib import Path
import struct
import unittest

from lupa.luajit21 import LuaRuntime
from lupa.lua54 import LuaRuntime as Lua54

ROOT=Path(__file__).resolve().parents[1]
# Native writer argument order, independently matched to OpenSHC's file fields.
PARTS=[(1008,[(4,0x1fe8678,0x2a7bb78,0x474775),(4,0x1fe867c,0x2a7bb7c,0x474782),
    (1000,0x1fe8680,0x2a7bb80,0x47474b)]),
    (8,[(4,0x1a269bc,0x24b9ebc,0x4747b3),(4,0x1a269c0,0x24b9ec0,0x4747c3)]),
    (28,[(4,0x1fe9244,0x2a7c744,0x4747e5),(20,0x1fe9248,0x2a7c748,0x4747f2),(4,0x1fe925c,0x2a7c75c,0x4747ff)]),
    (1017,[(4,0x1666d8c,0x1f99dd4,0x474824),(4,0x1666d90,0x1f99dd8,0x474831),
        (4,0x1fe9aa0,0x2a7cfa0,0x47483e),(1001,0x1fe8a68,0x2a7bf68,0x47484e),(4,0x1fe9aac,0x2a7cfac,0x47485b)]),
    (80,[(4,0x1fe923c,0x2a7c73c,0x474880),(4,0x1fe7d88,0x2a7b288,0x47488d),
        (4,0x1a26a08,0x24b9f08,0x47489a),(4,0x1fe9260,0x2a7c760,0x4748a7),(64,0x1a930d4,0x25265d4,0x4748b4)])]


def check_references(reader,variant):
    for _,parts in PARTS:
        for size,shc,extreme,reference in parts:
            address=shc if variant=='SHC' else extreme
            site=reference+(0 if variant=='SHC' else 0x230)
            assert reader(site,5)==b'\x68'+struct.pack('<I',address)


class WorldHeaderTests(unittest.TestCase):
    def prepare(self,variant,runtime=LuaRuntime):
        self.lua=runtime(encoding='latin-1',unpack_returned_tuples=True)
        g=self.lua.globals(); g.source_root=ROOT.as_posix()
        self.lua.execute('''
package.path=source_root..'/?.lua;'..package.path
header=require('code/world-header')
for i=1,20 do local name,value=debug.getupvalue(header.validate,i); if name=='groups' then groups=value end end
assert(groups)
''')
        self.references={}; self.memory={}; self.reads=[]; self.scans=[]; expected=[]
        self.addresses={}; self.sites=[]
        for index,(_,parts) in enumerate(PARTS,1):
            group=g.groups[index]; site=0x10000000+index*0x1000; self.sites.append(site)
            self.addresses[group.pattern]=site
            for offset,token in enumerate(group.pattern.split()):
                self.references[site+offset]=0x19 if token=='?' else int(token,16)
            for part_index,(size,shc,extreme,reference) in enumerate(parts,1):
                address=(shc if variant=='SHC' else extreme)+0x20000000
                operand=site+group.parts[part_index].operand
                for offset,value in enumerate(struct.pack('<I',address)): self.references[operand+offset]=value
                data=bytes((i+len(self.memory))%256 for i in range(size))
                self.memory[address]=data; expected.append(data)
        self.expected=b''.join(expected)
        def read(address,size):
            self.reads.append((address,size))
            return self.memory[address][:size].decode('latin-1')
        def scan(pattern,start=None):
            self.scans.append((pattern,start))
            return 0 if start else self.addresses[pattern]
        g.scan=scan
        g.read_reference=lambda a:struct.unpack('<I',bytes(self.references[a+i] for i in range(4)))[0]
        g.read_bytes=lambda a,n:self.lua.table_from(self.references[a+i] for i in range(n))
        g.read_data=read
        g.hash_string=lambda d:hashlib.sha256(d.encode('latin-1')).hexdigest()
        self.lua.execute('''
package.path=source_root..'/?.lua;'..package.path
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_reference,readString=read_data}
sha={sha256=hash_string}
''')

    def test_both_layouts_preserve_every_header_byte(self):
        for runtime in (LuaRuntime,Lua54):
            for variant in ('SHC','Extreme'):
                self.prepare(variant,runtime)
                raw,descriptor=self.lua.eval('header.read')()
                self.assertEqual(raw.encode('latin-1'),self.expected)
                self.assertEqual(len(raw),2141); self.assertEqual(len(self.reads),18)
                self.lua.eval('header.validate')(raw,descriptor)
                self.lua.eval('header.read')()
                self.assertEqual(len(self.scans),10)
                descriptor['fields'][2]['offset']=999
                with self.assertRaisesRegex(Exception,'field differs'):
                    self.lua.eval('header.validate')(raw,descriptor)

    def test_last_invalid_reference_prevents_all_data_reads(self):
        self.prepare('SHC'); self.lua.eval('header.read')(); self.reads=[]
        self.references[self.sites[-1]+79]+=4
        with self.assertRaisesRegex(Exception,'reference changed'):
            self.lua.eval('header.read')()
        self.assertEqual(self.reads,[])

    def test_short_header_read_is_rejected(self):
        self.prepare('Extreme'); self.memory[0x22a7bb80]=b'short'
        with self.assertRaisesRegex(Exception,'Short native'):
            self.lua.eval('header.read')()

    def test_invalid_discovery_or_operands_prevents_all_data_reads(self):
        for runtime in (LuaRuntime,Lua54):
            for case in ('missing','duplicate','modified','pointer','layout'):
                with self.subTest(runtime=runtime,case=case):
                    self.prepare('SHC',runtime)
                    if case=='missing': self.lua.execute('core.AOBScan=function() return 0 end')
                    elif case=='duplicate': self.lua.execute('core.scanForAOB=function() return 123 end')
                    elif case=='modified': self.references[self.sites[-1]+12]=0xcc
                    elif case=='pointer':
                        for i in range(4): self.references[self.sites[-1]+79+i]=0
                    elif case=='layout': self.references[self.sites[0]+60]+=4
                    with self.assertRaises(Exception): self.lua.eval('header.read')()
                    self.assertEqual(self.reads,[])
