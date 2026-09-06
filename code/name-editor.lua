-- Keyboard editing for a native-rendered replay dialog. Names never become paths.
local M={}
function M.new(value)
  value=type(value)=='string' and value:gsub('[^ -~]',''):sub(1,40) or ''
  return setmetatable({value=value,cursor=#value,selected=true},{__index=M})
end
function M:input(message,key)
  if message==0x100 then
    if key==37 then self.cursor=math.max(0,self.cursor-1); self.selected=false
    elseif key==39 then self.cursor=math.min(#self.value,self.cursor+1); self.selected=false
    elseif key==36 then self.cursor=0; self.selected=false
    elseif key==35 then self.cursor=#self.value; self.selected=false
    elseif key==46 then
      if self.selected then self.value=''; self.cursor=0
      else self.value=self.value:sub(1,self.cursor)..self.value:sub(self.cursor+2) end
      self.selected=false
    end
  elseif message==0x102 then
    if key==13 then return 'save' elseif key==27 then return 'cancel' end
    if key==8 or (key>=32 and key<=126) then
      if self.selected then self.value=''; self.cursor=0; self.selected=false end
      if key==8 then
        if self.cursor>0 then
          self.value=self.value:sub(1,self.cursor-1)..self.value:sub(self.cursor+1)
          self.cursor=self.cursor-1
        end
      elseif #self.value<40 then
        self.value=self.value:sub(1,self.cursor)..string.char(key)..self.value:sub(self.cursor+1)
        self.cursor=self.cursor+1
      end
    end
  end
end
function M:label()
  return self.selected and ('['..self.value..']')
    or (self.value:sub(1,self.cursor)..'|'..self.value:sub(self.cursor+1))
end
return M
