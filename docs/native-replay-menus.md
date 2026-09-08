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
