# Native replay dialogs

Replay dialogs reuse Crusader's original title banner and shield sprites from
`interface_icons3`. `PencilRenderCore::drawHeaderBanner` is called at 0x468FE0
in Crusader and 0x469210 in Extreme, after checking the original entry bytes.
The thiscall accepts four stack arguments and returns with `ret 0x10`.

Heading placement follows the original Options dialog: centered at y+22,
font 15, color 0xC2F0EB and blend 0. Labels still use the existing localized
replay strings. Controls and content move down 32 pixels, and the dialog grows
by the same amount, leaving the native 64-pixel tiled banner unobstructed.
The largest dialog remains within the game's 800x600 logical menu surface.

Playback status reads the existing pause flag and shows elapsed/total ticks and
scheduled/total recorded commands. Completion and failure take precedence over
pause, so a stopped replay cannot be described as merely paused. These are
presentation reads; opening the dialog does not change replay scheduling.

The optional original-executable test runs both native banner routines at the
two dialog widths and checks tile positions, shield calls, stack cleanup and
preserved registers. Texture blitting is a stand-in; it does not establish
actual pixel output. Menu-flow tests cover pause/completion/failure precedence
and the layout offsets. Live visual checks must use the installed build.

Live 0.33.0 checks passed for the German library, rename/cancel and removal
confirmation/cancel with Ascension and Automarket loaded. A natural defeat
exposed a separate lifecycle gap: returning from results to the Skirmish lobby
left the session open and the new recording unavailable. The existing checked
`GameCore::switchToMenuView` observer only handled manual quit's view 61.

Version 0.33.1 also finalizes on lobby view 20 and main-menu view 41, using the
last observed simulation boundary. It does not treat the in-game build/report
views (14/16) or rankings (58) as exits, and does nothing during snapshot loading.
No new native detour is installed. The regression covers finalization, selection
of the full recording, repeated transitions and the excluded views/loading path.
