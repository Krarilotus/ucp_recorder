-- Shared bounded file copies for single-player and multiplayer snapshots.
-- Callers own manifest publication and failure state; this owner closes both
-- handles and copies exactly the selected, already-flushed source prefix.
local M={}
function M.copy(source,target,size)
  local input=assert(io.open(source,'rb'))
  local output,err=io.open(target,'wb')
  if not output then input:close(); error(err) end
  local ok,reason=pcall(function()
    local remaining=size or assert(input:seek('end'))
    assert(type(remaining)=='number' and remaining>=0 and remaining%1==0,'Invalid replay copy size')
    assert(input:seek('set',0))
    while remaining>0 do
      local chunk=assert(input:read(math.min(remaining,65536)),'Capture prefix ended early')
      assert(#chunk>0 and #chunk<=remaining,'Invalid capture prefix')
      assert(output:write(chunk)); remaining=remaining-#chunk
    end
  end)
  local a,b=input:close(),output:close()
  assert(ok and a and b,reason or 'Cannot close capture copy')
end
return M
