# Replay follow-up work

The RNG2 failure at tick 22,912 remains the blocking determinism issue. Version
0.30.0 adds attribution; 0.31.0 includes the separately prepared menu work.

- [ ] Verify the church-panel RNG fix in a fresh recorded match, including pause,
  speed changes, allied requests and Automarket. Repeat on Extreme.
- [ ] Clearly distinguish failed playback from verified completion. Resuming a
  halted replay must not allow ghost placement or other apparent game actions.
- [ ] Keep camera, pause/speed, book, popularity/economy reports and unit/building
  inspection usable while preventing gameplay mutations during playback.
- [ ] Live-verify the 0.31.0 replay-only player-view selector across book/report
  tabs and all occupied slots. Native summary/identity tests pass; input context
  and all rendering side effects still need broader inspection.
- [ ] Visually verify the 0.31.0 native fonts, centered labels, disabled states,
  English/German text, removal and keyboard flow at supported resolutions.
- [x] Label full automatic recordings separately from named snapshots and select
  the newly completed full source recording (implemented in 0.31.0).
- [ ] Support offline playback of both host and client multiplayer recordings in
  the single-player browser, with their recorded settings. This still needs
  initial-world/identity capture, immediate/system/resync handling, extension
  state restoration and tests on two physical peers.

These items are outstanding work, not claims about the current release.
