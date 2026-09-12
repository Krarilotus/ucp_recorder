-- Keep the game's history renderer and action handlers. Bind their existing
-- data-source operands before Recorder redirects them to its merged catalogue.
local M={}
local binding,guards
function M.resolve()
  if binding then return binding end
  local check=require('code/hook-check')
  local patterns=require('code/history-patterns')
  local result=require('code/result-sites').resolve()
  local state=require('code/engine-state-sites').resolve()
  local commands=require('code/native-command').bind({}).commands
  local menu=require('code/load-sites').resolve().menuTransition.guard.address
  local g={prepare=check.resolve(patterns.prepare,'Recorder history preparation'),
    frame=check.resolve(patterns.frame,'Recorder history renderer')}
  local function integer(a) return core.readInteger(a) end
  local function relative(a) return a+5+integer(a+1) end
  local p,f=g.prepare.address,g.frame.address
  local a=p+48
  g.action=check.context(a,patterns.action,'Recorder history actions')
  g.rows=check.context(f+0x1d5,patterns.rows,'Recorder history rows')
  g.help=check.context(f+0x8a3,patterns.help,'Recorder history hover text')
  local sorter=relative(p)
  g.sort=check.context(sorter,patterns.sort,'Recorder native history sorting')
  local savedMode=integer(p+43)
  local scroll=integer(a+12)
  local count=integer(a+38)
  local index=integer(a+0x63)
  local sort=integer(a+0x224)
  for name,value in pairs({savedMode=savedMode,scroll=scroll,count=count,index=index,sort=sort}) do
    require('code/validation').integer(value,0x10000,0x7fffffff-1000,'Native history '..name)
  end
  assert(integer(p+38)==commands.handler+0x618 and integer(p+13)==state.gameCore+0x2380
    and integer(a+0x8a)==state.gameCore+0x68 and integer(a+0x94)==commands.handler+0x618
    and integer(a+0x82)==result.statistics.results,
    'Recorder history preparation disagrees with native owners')
  assert(integer(sorter+4)==result.storedCount and integer(sorter+0x2f)==result.records
    and integer(sorter+0x59)==result.records and integer(sorter+0x79)==sort
    and integer(sorter+0x92)==count and integer(sorter+0xae)==index
    and integer(sorter+0xc0)==count and relative(a+0x24c)==sorter and relative(a+0x29d)==sorter,
    'Recorder history sorting contexts disagree')
  for _,offset in ipairs({25,47,59,77,0x1ae,0x25f,0x266,0x2b0,0x2b7}) do
    assert(integer(a+offset)==scroll,'Recorder history scroll operands disagree')
  end
  for _,offset in ipairs({0x56,0x1b8,0x252,0x2a3}) do
    assert(integer(a+offset)==count,'Recorder history count operands disagree')
  end
  assert(integer(a+0x22b)==sort and integer(a+0x1f9)==savedMode and integer(a+0x20c)==savedMode
    and integer(a+0x1fe)==commands.handler+0x618 and integer(a+0x211)==commands.handler+0x618
    and integer(a+0x195)==state.gameCore and integer(a+0x19b)==state.gameCore+0x2377
    and integer(a+0x1eb)==state.gameCore and relative(a+0x1a0)==menu
    and relative(a+0x1f3)==menu and relative(a+0x206)==menu,
    'Recorder history results/return contexts disagree')
  assert(integer(g.rows.address+2)==scroll and integer(g.help.address+56)==scroll,
    'Recorder history renderer scroll differs')
  local function site(context,offset,size)
    return {address=context.address+offset,bytes=core.readBytes(context.address+offset,size),guard=context}
  end
  local operands={}
  local function operand(context,offset,size,field,kind,delta)
    local s=site(context,offset,size)
    s.offset=field;s.kind=kind;s.delta=delta
    assert(integer(s.address+field)==(kind=='index' and index or result.records)+delta,
      'Recorder history data-source operand differs')
    operands[#operands+1]=s
  end
  operand(g.rows,8,7,3,'index',0);operand(g.rows,21,6,2,'records',0)
  operand(g.help,66,7,3,'index',0);operand(g.help,79,6,2,'records',0)
  operand(g.action,0x60,7,3,'index',0)
  operand(g.action,0x6d,7,2,'records',0x440)
  operand(g.action,0x76,6,2,'records',0x478)
  operand(g.action,0xa2,7,2,'records',0x460)
  operand(g.action,0x131,7,2,'records',0x460)
  operand(g.action,0x1be,7,3,'index',0)
  binding={records=result.records,storedCount=result.storedCount,index=index,count=count,
    scroll=scroll,sort=sort,savedMode=savedMode,prepareList=site(g.prepare,0,5),
    prepare=site(g.prepare,5,7),action=site(g.action,0,5),frame=site(g.frame,0,6),
    helpText=site(g.help,50,5),operands=operands}
  guards=g
  return binding
end
function M.verify()
  local result=M.resolve()
  for name,guard in pairs(guards) do
    require('code/hook-check').verify(guard,'Recorder history context changed: '..name)
  end
  return result
end
return M
