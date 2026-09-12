"""Compare the schema with private original tables, then relocate their pointers."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from lupa.lua54 import LuaRuntime
from check_executables import image_reader
from native_save_fixture import native_save_fixture


def check(path,variant):
    root=Path(__file__).resolve().parents[1]
    raw=image_reader(path)(native_save_fixture(variant)['sections'],1968)
    lua=LuaRuntime(unpack_returned_tuples=True,encoding='latin-1')
    lua.globals().source_root=root.as_posix()
    lua.globals().hash_data=lambda data:hashlib.sha256(data.encode('latin-1')).hexdigest()
    lua.execute("package.path=source_root..'/?.lua;'..package.path; sha={sha256=hash_data}")
    decode=lua.eval("require('code/world-layout').decode")
    entries,profile=decode(raw,variant)
    assert len(entries)==122 and profile.hash==hashlib.sha256(raw).hexdigest()
    moved=bytearray(raw)
    for i in range(122):
        address=struct.unpack_from('<I',raw,i*16)[0]
        struct.pack_into('<I',moved,i*16,address+0x10000000)
    relocated,identity=decode(bytes(moved),variant)
    assert identity.total==profile.total and identity.hash!=profile.hash
    for i in range(1,123):
        assert relocated[i].address==entries[i].address+0x10000000
        for field in ('size','section','compressed','offset'): assert relocated[i][field]==entries[i][field]
    return dict(variant=variant,referenceSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                sections=122,total=profile.total,originalTableHash=profile.hash,
                relocatedTableHash=identity.hash,liveGame=False)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--variant',choices=['SHC','Extreme'],required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); result=check(a.reference,a.variant)
    a.output.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
