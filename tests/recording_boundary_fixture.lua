-- Session tests model memory ownership; test_recording_boundary.py executes the
-- emitted native copier and verifies its actual bytes and calling convention.
return function(engine)
  return {
    clear=function(self) self.valid=false; self.rng=nil; self.resources=nil; self.state=nil end,
    capture=function(self)
      self.rng=engine:rngData(); self.resources=engine:resourceData(); self.state=engine:rngState()
      self.valid=true
    end,
    read=function(self) assert(self.valid); return self.rng,self.resources end,
    rngState=function(self) assert(self.valid); return self.state end,
  }
end
