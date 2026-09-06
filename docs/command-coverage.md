# Native command coverage

Recorder uses the game's command queue and original dispatcher. It stores the
payload and execution tick, validates them, then schedules the same native
command during playback. It does not reimplement building, troop or economy
actions. The validation list must describe all supported timed gameplay commands;
an incomplete list stops an otherwise valid recording.

## Production-switch failure and repair

A live 0.28.0 capture stopped with `Unsupported replay command category 33`
after changing smith production. This is a validation failure, not evidence of
an RNG desync or a process crash. Command 33 is the common building-production
handler, also applicable to fletchers and poleturners. Its seven-byte payload is
building ID (uint16), product (uint8), building UID (uint32). The native action
updates the building's product only if its UID still matches. The recorder now
accepts this layout and leaves that check to the original game code.

Version 0.29.0 also admits commands 37, 72, 73, 74, 75, 76, 79, 86 and 97.
Their native handlers cover drawbridges, siege/group selection, dogs, tower siege
removal, wall/pitch removal, unit-linkage recalculation, ammunition and braziers.
Command 76 carries a 13-byte header plus a 1,200-byte placement array; the native
action reads the transmitted array, so playback must preserve the entire payload.

## Complete table audit

The table below covers the 120 original command entries, 0 through 119. Addresses
are virtual addresses in the original 1.41 executables. Names are reverse-engineered
labels from the OpenSHC Ghidra project, not a claim that every action has a C++
reimplementation. Both variants' original receive-phase handlers were executed
in Unicorn to establish payload size and whether they retain the command tick.
`immediate` means the native handler clears the timestamp; `no-op` means it did
not declare a payload. Neither belongs in the timed playback stream.

The timed exclusions are deliberate: removed commands 8/30/32; native save/load
39; resync 54; player disconnection 77; multiplayer alliance changes 83; and
Extreme tactical powers 119 when the recorded variant is standard Crusader.
This remains single-player replay coverage. Offline multiplayer playback needs
explicit handling of network lifecycle effects, actors and immediate events;
enabling those command numbers alone would not implement it.

Categories 120/121 are outside the original table. Category 122 is the separately
validated Automarket/protocol extension, documented in [Automarket replay](automarket-replay.md).

| ID | Native label | SHC handler / bytes | Extreme handler / bytes | Recorder policy |
| --- | --- | --- | --- | --- |
| 0 | DoNothing | `0x469f10` / — | `0x402ae0` / — | no-op |
| 1 | DoNothing | `0x469f10` / — | `0x402ae0` / — | no-op |
| 2 | InitialAnnounceToHost | `0x4893c0` / 0 | `0x4894d0` / 0 | immediate |
| 3 | InitialAnnounceReply | `0x480640` / 0 | `0x480810` / 0 | immediate |
| 4 | AskForPlayerSlotAssignment | `0x48f870` / 1 | `0x48f980` / 1 | immediate |
| 5 | AssignPlayerIDToPlayerSlot | `0x489410` / 4 | `0x489520` / 4 | immediate |
| 6 | HostShareLobbyState | `0x48faa0` / 170 | `0x48fbb0` / 170 | immediate |
| 7 | AnnounceGameVersion | `0x480680` / 4 | `0x480850` / 4 | immediate |
| 8 | _REMOVED_COMMAND1_ | `0x482280` / 0 | `0x4823b0` / 0 | excluded timed |
| 9 | TriggerLobbyPlayerInformationRefresh | `0x4894f0` / 8 | `0x489600` / 8 | immediate |
| 10 | AnnouncePlayerInformationSuchAsNameLordTypeAndAvailableAIVS | `0x480710` / 592 | `0x4808e0` / 592 | immediate |
| 11 | ShareGameSeedAndMultiplayerSettingsAndStartGame | `0x480980` / 2012 | `0x480b50` / 2012 | immediate |
| 12 | CommandCheckSync | `0x480b10` / 10 | `0x480ce0` / 10 | immediate |
| 13 | AnnounceTeamsAndPositions | `0x480be0` / 33 | `0x480db0` / 33 | immediate |
| 14 | ClickTauntOrChat | `0x4895e0` / 544 | `0x4896f0` / 544 | immediate |
| 15 | ClickNavigateMenuOrEscape | `0x480db0` / 4 | `0x480f80` / 4 | timed, both |
| 16 | MakeUnitSelection | `0x480e60` / 402 | `0x481030` / 1252 | timed, both |
| 17 | ClickMoveUnit | `0x480f00` / 8 | `0x4810d0` / 8 | timed, both |
| 18 | ClickErase | `0x481050` / 5 | `0x481220` / 5 | timed, both |
| 19 | ClickSetLand | `0x481120` / 5 | `0x4812f0` / 5 | timed, both |
| 20 | ClickRaiseLand | `0x481250` / 6 | `0x481420` / 6 | timed, both |
| 21 | ClickSetTerrain | `0x4813c0` / 10 | `0x481590` / 10 | timed, both |
| 22 | ClickHeightEqualize | `0x481580` / 6 | `0x481750` / 6 | timed, both |
| 23 | ClickTerrainHeightMinOrMax | `0x4816f0` / 6 | `0x4818c0` / 6 | timed, both |
| 24 | ClickCreatePlateau | `0x481860` / 6 | `0x481a30` / 6 | timed, both |
| 25 | ClickPlaceWall | `0x4819d0` / 12 | `0x481ba0` / 12 | timed, both |
| 26 | ClickPlaceRockOrTree | `0x481b50` / 6 | `0x481d20` / 6 | timed, both |
| 27 | ClickRaiseLand2Unk | `0x481c80` / 6 | `0x481e50` / 6 | timed, both |
| 28 | ClickPlaceBuilding | `0x481d90` / 10 | `0x481f60` / 10 | timed, both |
| 29 | ClickDestroyBuilding | `0x481f40` / 7 | `0x482110` / 7 | timed, both |
| 30 | _REMOVED_COMMAND1_ | `0x482280` / 0 | `0x4823b0` / 0 | excluded timed |
| 31 | ClickRecruitUnit | `0x4821e0` / 3 | `0x4823c0` / 3 | timed, both |
| 32 | _REMOVED_COMMAND1_ | `0x482280` / 0 | `0x4823b0` / 0 | excluded timed |
| 33 | ClickSetBuildingProductionType | `0x482290` / 7 | `0x482460` / 7 | timed, both |
| 34 | ClickChangeTaxes | `0x482360` / 1 | `0x482530` / 1 | timed, both |
| 35 | ClickChangeRations | `0x4823c0` / 1 | `0x482590` / 1 | timed, both |
| 36 | ClickGiveUnitsInstruction | `0x482420` / 15 | `0x4825f0` / 15 | timed, both |
| 37 | ClickSomethingWithDrawBridgeUnk | `0x482550` / 7 | `0x482720` / 7 | timed, both |
| 38 | ClickBuyOrSell | `0x482620` / 2 | `0x4827f0` / 2 | timed, both |
| 39 | AutoSaveTriggered | `0x489880` / 75 | `0x489990` / 75 | excluded timed |
| 40 | SetPlayerNameUnk | `0x489ac0` / 66 | `0x489bd0` / 66 | immediate |
| 41 | ClickDestroy | `0x4826c0` / 5 | `0x482890` / 5 | timed, both |
| 42 | ClickPlaceSiegeTent | `0x4827e0` / 7 | `0x4829b0` / 7 | timed, both |
| 43 | ClickBuildingSleep | `0x482a40` / 2 | `0x482c10` / 2 | timed, both |
| 44 | ClickCreateAnimal | `0x482aa0` / 5 | `0x482c70` / 5 | timed, both |
| 45 | ClickOpenOrCloseGate | `0x482bb0` / 7 | `0x482d80` / 7 | timed, both |
| 46 | ShareDesyncedHashes | `0x482c80` / 0 | `0x482e50` / 0 | immediate |
| 47 | CommandChangeMapSelection | `0x483290` / 2004 | `0x483460` / 2004 | immediate |
| 48 | CommandLoadMapHeader | `0x489c80` / 1008 | `0x489d90` / 1008 | immediate |
| 49 | AcknowledgeMapExistence | `0x4833f0` / 8 | `0x4835c0` / 8 | immediate |
| 50 | SubmitMSVMapIndexAndProperties | `0x489e30` / 2012 | `0x489f40` / 2012 | immediate |
| 51 | ShareMSVMapIndex | `0x4834b0` / 8 | `0x483680` / 8 | immediate |
| 52 | ClickInitOrChangeGameIntensityAndBalance | `0x483570` / 80 | `0x483740` / 88 | immediate |
| 53 | SharePlayerName | `0x483850` / 16 | `0x483a80` / 16 | immediate |
| 54 | ResyncStartCS_CS_Sub | `0x48fc20` / 8 | `0x48fd30` / 8 | excluded timed |
| 55 | ResyncResumeCS | `0x48fcb0` / 64 | `0x48fdc0` / 64 | immediate |
| 56 | ResyncChimp | `0x48a0e0` / 1172 | `0x48a1f0` / 1172 | immediate |
| 57 | SendResyncBuilding | `0x48a1f0` / 816 | `0x48a300` / 816 | immediate |
| 58 | SendResyncVeg | `0x48a2a0` / 160 | `0x48a3b0` / 160 | immediate |
| 59 | SendResyncTribe | `0x48a350` / 824 | `0x48a460` / 1676 | immediate |
| 60 | SendResyncPlayerData | `0x48a460` / 14840 | `0x48a570` / 14840 | immediate |
| 61 | SendResyncUnknown | `0x48a510` / 14570 | `0x48a620` / 29570 | immediate |
| 62 | SendResyncEntity | `0x48a710` / 236 | `0x48a820` / 236 | immediate |
| 63 | SendResyncCharLayer | `0x483a00` / 2520 | `0x483c30` / 2520 | immediate |
| 64 | ResyncShortLayer | `0x4840c0` / 2520 | `0x4842f0` / 2520 | immediate |
| 65 | SendResyncIntLayer | `0x48a7c0` / 2520 | `0x48a8d0` / 2520 | immediate |
| 66 | ResyncStatus2 | `0x4843f0` / 0 | `0x484620` / 0 | immediate |
| 67 | ResetSyncStatusUnk | `0x484450` / 0 | `0x484680` / 0 | immediate |
| 68 | ClickRepairTower | `0x4844a0` / 10 | `0x4846d0` / 10 | timed, both |
| 69 | CommandSpawnEntity | `0x4845b0` / 9 | `0x4847e0` / 9 | timed, both |
| 70 | ClickUnitStance | `0x4847b0` / 3 | `0x4849e0` / 3 | timed, both |
| 71 | ClickExtendRallyPoint | `0x484850` / 7 | `0x484a80` / 7 | timed, both |
| 72 | SiegeEngineRelated | `0x484960` / 4 | `0x484b90` / 4 | timed, both |
| 73 | TribeRelated1 | `0x484a00` / 2 | `0x484c30` / 2 | timed, both |
| 74 | ReleaseDogs | `0x484a70` / 6 | `0x484ca0` / 6 | timed, both |
| 75 | RemoveTowerSiegeEngine | `0x484b10` / 4 | `0x484d40` / 4 | timed, both |
| 76 | DestroyWallOrPitch | `0x484c40` / 1213 | `0x484e70` / 1213 | timed, both |
| 77 | DestroyPlayer | `0x48a8a0` / 4 | `0x48a9b0` / 4 | excluded timed |
| 78 | DeselectUnit | `0x484da0` / 2 | `0x484fd0` / 2 | timed, both |
| 79 | TriggerRecalculationOfUnitSameTileLinkage | `0x484e10` / 1 | `0x485040` / 1 | timed, both |
| 80 | ResyncMoat | `0x48aa80` / 1604 | `0x48ab90` / 1604 | immediate |
| 81 | ResyncTeleClimb | `0x48ab40` / 520 | `0x48ac50` / 520 | immediate |
| 82 | ResyncPitch | `0x48abf0` / 2004 | `0x48ad00` / 2004 | immediate |
| 83 | CommandSwitchTeams | `0x48acb0` / 3 | `0x48adc0` / 3 | excluded timed |
| 84 | ResyncZone | `0x484e70` / 6404 | `0x4850a0` / 6404 | immediate |
| 85 | KickPlayerUnk | `0x484f30` / 4 | `0x485160` / 4 | immediate |
| 86 | CommandSelectionReplenishAmmo | `0x485020` / 3 | `0x485250` / 3 | timed, both |
| 87 | SyncRelatedSomething | `0x48b170` / 8 | `0x48b280` / 8 | immediate |
| 88 | BroadCastSyncRelatedStatus | `0x4850e0` / 0 | `0x485310` / 0 | immediate |
| 89 | VoteKick_K_D_B_G_J | `0x485140` / 4 | `0x485370` / 4 | immediate |
| 90 | SyncPacketSizeAnnouncement | `0x485210` / 12 | `0x485440` / 12 | immediate |
| 91 | SendQuitGameQuestion | `0x48b280` / 0 | `0x48b390` / 0 | immediate |
| 92 | ShareQuitGameVote | `0x48b330` / 4 | `0x48b440` / 4 | immediate |
| 93 | ShareAnnouncementWithHost | `0x4852d0` / 0 | `0x485500` / 0 | immediate |
| 94 | CloseModalDialogForEveryone | `0x485330` / 0 | `0x485560` / 0 | immediate |
| 95 | VoteKick_SEND_L_E_C_A_F_H_ZAP | `0x48b4e0` / 4 | `0x48b5f0` / 4 | immediate |
| 96 | SomePlayerNameUpdateCommand | `0x485380` / 500 | `0x4855b0` / 500 | immediate |
| 97 | FlagsAndBraziersCommandUnk | `0x485520` / 4 | `0x485750` / 4 | timed, both |
| 98 | NotifyLaggingPlayer | `0x4855c0` / 2 | `0x4857f0` / 2 | immediate |
| 99 | SomeKindOfMultiplayerPingUnk | `0x485650` / 2 | `0x485880` / 2 | immediate |
| 100 | ShareGameStatePartialHashes | `0x4856e0` / 48 | `0x485910` / 48 | immediate |
| 101 | ResyncStatusStart | `0x485790` / 14 | `0x4859c0` / 14 | immediate |
| 102 | SetUnitAssemblyPoint | `0x485830` / 5 | `0x485a60` / 5 | timed, both |
| 103 | ShareMapHashForMapName | `0x48b6c0` / 1004 | `0x48b7d0` / 1004 | immediate |
| 104 | StartSendingMapFile | `0x485c10` / 1 | `0x485e40` / 1 | immediate |
| 105 | StartReceivingMapFile | `0x485cc0` / 1004 | `0x485ef0` / 1004 | immediate |
| 106 | ShareMapPart | `0x48b8f0` / 1029 | `0x48ba00` / 1029 | immediate |
| 107 | MapSendingRelated | `0x485e80` / 1 | `0x4860b0` / 1 | immediate |
| 108 | DoNothing | `0x469f10` / — | `0x402ae0` / — | no-op |
| 109 | DoNothing | `0x469f10` / — | `0x402ae0` / — | no-op |
| 110 | HostAnnounceRoundTable | `0x485f20` / 19 | `0x486150` / 19 | immediate |
| 111 | DoNothing | `0x469f10` / — | `0x402ae0` / — | no-op |
| 112 | AddAIPlayer | `0x486040` / 12 | `0x486270` / 12 | immediate |
| 113 | SendPlayerToPlayerRequestOrResponse | `0x486140` / 18 | `0x486370` / 18 | timed, both |
| 114 | ResyncVillage | `0x48bbe0` / 28060 | `0x48bcf0` / 28060 | immediate |
| 115 | ResyncAIZone | `0x48bc90` / 3844 | `0x48bda0` / 3844 | immediate |
| 116 | ShareAIVHash | `0x486320` / 512 | `0x486550` / 512 | immediate |
| 117 | UpdateSkirmishGameMenuFaceBitmap | `0x4863a0` / 136 | `0x4865d0` / 136 | immediate |
| 118 | HostRemoveAIPlayerBySlotID | `0x48ffd0` / 4 | `0x4900e0` / 4 | immediate |
| 119 | ActiveTacticalPowers | `0x486530` / 8 | `0x486760` / 8 | timed, Extreme only |

## Reproducible checks and limits

Run `python tests/check_executables.py <original-game-directory>` with both
executables. `check_command_layouts_native.py` audits every original entry and
fails if an omitted timed handler lacks an explicit exclusion. Supported layouts
are also checked at the first and last ring slots with three timestamps.
`check_production_native.py` executes the original production serializer,
dispatcher handler and UID-checked action without replacing any callees: 324
state-change cases per variant cover both ring endpoints, multiple buildings,
product values and matching/mismatched UIDs. Synthetic product values test byte
transport; they do not imply every value is a valid in-game product.

Lua regression tests capture and schedule all ten newly admitted payloads,
including nonuniform binary data in the 1,213-byte wall/pitch command, and reject
short/long payloads. These checks establish command coverage and production
behavior. They do not establish whole-match determinism or validate multiplayer
playback. Optional native-binary checks run locally; the public CI does not bundle
the proprietary game executables.

Original executable SHA-256 values used for this audit:

- `Stronghold Crusader.exe`: `3bb0a8c1e72331b3a30a5aa93ed94beca0081b476b04c1960e26d5b45387ac5a`
- `Stronghold_Crusader_Extreme.exe`: `55648e6b05d67d37a5773fe699bbb17a2d6ad4de1bb9dbded9a21caef82bd7fb`

## Focused live regression

Start a fresh recording using 0.29.0. Change a working smith between swords and
maces, a fletcher between bows and crossbows, and a poleturner between spears and
pikes. Use rally points, drawbridges, dog cages, tower siege equipment, wall/pitch
deletion and fire ammunition where available. Verify normal trade, recruitment
and ally controls still work. Save a named copy, continue playing, and quit the
mission normally to finish the full automatic recording. Replay that full capture
once with minimal interaction, then again while pausing and changing speed.
Check completion and checkpoint results; absence of a popup alone is insufficient.

A recording already marked failed remains incomplete. This release cannot
reconstruct actions that an older recorder stopped capturing.
