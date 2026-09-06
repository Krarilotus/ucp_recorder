# Replay follow-up work

Fix and verify the reproducible single-player divergence before expanding the UI.

- [ ] Verify the church-panel RNG fix in a fresh recorded match, including pause,
  speed changes, allied requests and Automarket. Repeat on Extreme.
- [ ] Clearly distinguish failed playback from verified completion. Resuming a
  halted replay must not allow ghost placement or other apparent game actions.
- [ ] Keep camera, pause/speed, book, popularity/economy reports and unit/building
  inspection usable while preventing gameplay mutations during playback.
- [ ] Add a replay-only player-view selector. Viewing another player must not
  change recorded command ownership or grant the spectator gameplay control.
- [ ] Match native menu fonts, centered labels, button sizes and title styling.
- [ ] Distinguish full automatic recordings from named checkpoint copies, and
  select the newly completed full recording when returning to the browser.
- [ ] Support offline playback of both host and client multiplayer recordings in
  the single-player browser, with their recorded settings. This still needs
  initial-world/identity capture, immediate/system/resync handling, extension
  state restoration and tests on two physical peers.

These items are outstanding work, not claims about the current release.
