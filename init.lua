local native = require("code/native")
local fixes = require("code/fixes")
local ui = require("code/ui")
local recorder = require("code/recorder")

return {
	enable = function(self, config)

		--- Init ---

	  require("code/native").verify()
		fixes.apply()
		local gameRecorder = recorder:new({name = "test_recording1", rngLogMethod = config.rngLogMethod})
		ui.createButtons(gameRecorder)

		--- Injections ---

		-- skirmish startup injects
		core.detourCode(function(registers)
			gameRecorder:onStartSkirmish(registers)
			ui.resetButtons()
            return registers
		end, native.addr(0x004428b5), 6)

		core.writeCode(native.addr(0x00442877), {0x90, 0x90, 0x90, 0x90, 0x90, -- make space for detourCode
																0x90, 0x90, 0x90, 0x90, 0x90})
		core.detourCode(function(registers) return gameRecorder:onBeforeSetMatchSeed(registers) end, native.addr(0x00442877), 10)

		core.detourCode(function(registers)
			return gameRecorder:onCustomSkirmishGame(registers)
		end, native.addr(0x0042bf4c), 6)

		-- after LaunchGame()
		core.detourCode(function(registers)

		return registers
		end, native.addr(0x004428c6), 10)

		-- skirmish end injects

		-- on switchToMenu
		core.detourCode(function(registers)
			local DAT_CurrentMenuID = core.readInteger(native.addr(0x01fe7d1c))
			local newMenuID = registers.EBP

			if newMenuID == 61 then
				print("ingame menu change - exited match?")
				print("Old menu: " .. DAT_CurrentMenuID)
				print("New menu: " .. newMenuID)
				print("onMenuChange")
				if gameRecorder.mode == "record" then
					print("stopping recording")
					gameRecorder:stopRecording()
				elseif gameRecorder.mode == "play" then
					print("stopping playback")
					gameRecorder:stopPlayback()
				end
			end

		return registers
		end, native.addr(0x0046b358), 6)

		-- on loadGame
		core.detourCode(function(registers)
			print("onLoadGame")
			if gameRecorder.mode == "record" then
				print("stopping recording")
				gameRecorder:stopRecording()
			elseif gameRecorder.mode == "play" then
				print("stopping playback")
				gameRecorder:stopPlayback()
			end

		return registers
		end, native.addr(0x00495337), 6)

		-- on restartGame
		core.detourCode(function(registers)
			print("onRestartGame")
			if gameRecorder.mode == "record" then
				print("stopping recording")
				gameRecorder:stopRecording()
			elseif gameRecorder.mode == "play" then
				print("stopping playback")
				gameRecorder:stopPlayback()
			end

		return registers
		end, native.addr(0x00494ba5), 5)

		-- consuming recorded commands function
		local scheduleNextCommandAddress = core.allocateCode({
			0x90, 0x90, 0x90, 0x90, 0x90,
			0xC3,
		})

		core.detourCode(function(registers) return gameRecorder:scheduleNextCommand(registers) end, scheduleNextCommandAddress, 5)

		gameRecorder._scheduleCommand = core.exposeCode(native.addr(0x00480210), 5, 1)

		-- schedule saved commands when in PLAYBACK mode
		-- gets called every tick
		core.insertCode(native.addr(0x00490690), 8,
										gameRecorder:onReceiveAllTransmittedCommandsASM(scheduleNextCommandAddress),
										nil, "after")

		-- process sent commands
		core.detourCode(function(registers) return gameRecorder:onTransmitCommand(registers) end, native.addr(0x00487c50), 6)

		-- process received commands
		core.detourCode(function(registers) return gameRecorder:onScheduleCommand(registers) end, native.addr(0x00480353), 6)

		--- fakes multiplayerIDs in singleplayer skirmish
		-- nop and detour to prevent original code execution
		core.writeCode(native.addr(0x0047eaf0), {
			0x90, 0x90, 0x90, 0x90, 0x90,
			0x90,
		})
		core.detourCode(function(registers) return gameRecorder:fakeMultiplayerIdentities(registers) end, native.addr(0x0047eaf0), 6)

		-- Do not set DAT_QueuedCommandPlayer to -1 in Singleplayer skirmish
		core.writeCode(native.addr(0x004876a6), {0x90,0x90,0x90,0x90,0x90,0x90,})

		--- Debugging and Logging ---

		local syncCheckAddress = core.allocateCode({
		 0x90, 0x90, 0x90, 0x90, 0x90,
		 0xC3,
		})

		core.detourCode(function(registers) return gameRecorder:syncCheck(registers) end, syncCheckAddress, 5)

		if config.rngLogMethod == "trace" then
			local traceRNG1 = true
			local traceRNG2 = true -- remove

			local rngFunction1 = native.addr(0x0046a800)
			local rngFunction2 = native.addr(0x0046a7d0)

			if traceRNG1 then core.detourCode(function(registers) return gameRecorder:syncCheck(registers, 1) end, rngFunction1, 6) end

			if traceRNG2 then core.detourCode(function(registers) return gameRecorder:syncCheck(registers, 2) end, rngFunction2, 6) end

		end

		-- optional
		-- Makes every game's RNG use the same seed
		if config.useFixedSeed then

			core.detourCode(function(registers)

				registers.EAX = require("code/validation").integer(config.fixedSeed, -2147483648, 2147483647, "fixed seed")

				return registers
			end, native.addr(0x0046a74a), 6)

		end

	end,

	disable = function(self, config)
	end,
}
