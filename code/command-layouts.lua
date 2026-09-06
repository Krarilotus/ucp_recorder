-- Native 1.41 handlers declare these fixed timed payload sizes in receive phase.
-- Command 14 (chat/taunt) instead uses the immediate fixed buffer and time zero.
local common={
  [15]=4,[17]=8,[18]=5,[19]=5,[20]=6,[21]=10,[22]=6,[23]=6,[24]=6,
  [25]=12,[26]=6,[27]=6,[28]=10,[29]=7,[31]=3,[34]=1,[35]=1,[36]=15,
  [38]=2,[41]=5,[42]=7,[43]=2,[44]=5,[45]=7,[68]=10,[69]=9,[70]=3,
  [71]=7,[78]=2,[113]=18,
}
local variants={SHC={[16]=402},Extreme={[16]=1252,[119]=8}}
return function(category,variant)
  local extra=assert(variants[variant],'Unsupported replay game variant')
  return extra[category] or common[category]
end
