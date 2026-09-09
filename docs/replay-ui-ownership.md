# Replay controls and native screen ownership

History belongs to the game's battle-history menu (view58). Replay contributes
the catalogue, selection outline, rename action and play hand. The original
renderer continues to own rows, portraits, scrolling, sort labels, hover
descriptions, the game count and navigation to statistics.

The 800×600 history canvas has eight rows ending at y508. Native footer text
starts at (175,522), with the game count at (175,550); the former help area starts
at (450,522). Added controls stay outside these existing rows and the scrollbar.
The native Back hand is GM150/picture69 at (10,460), but its visible footprint is
only (53,526)–(150,573). Replay mirrors that footprint horizontally. Picture71's
transparent padding is excluded from its hit rectangle, so clicking the final
history row still selects that row. The right hand has no extra subtitle.

In-game viewing belongs to presentation. The portrait strip changes only the
selected view; existing scoped native renderers read that player's book and
summary, then restore the recorded actor. Tick status is always drawn during
playback. F3 toggles recorded configuration details. Neither operation changes
the command stream, pause state or simulation speed.

## Surfaces and render passes

The original WinMain loop renders the map, then menu items, then modal dialogs.
Its final menu-item pass runs even when the build panel is not being redrawn.
`TextureRenderCore::moveOverlappingMenuPartsToMapSurface` (SHC 0x454F00) copies
only the native tab's specified overlap rectangles from SCREEN_MENU into the
map. It does not composite arbitrary top-corner or left-edge menu pixels.

Consequently front-end overlays draw to SCREEN_MENU (0), and in-game overlays
draw to MAP_GAME (1). Each callback restores the previous target, including on
failure. Native text uses -1 for right alignment; 2 is not a right-alignment
constant. These contracts are documented in OpenSHC's RenderTarget and
TextAlignment definitions and checked against the original SHC executable.

Portable regressions cover surface restoration, native text alignment, F3 and
portrait actions, footer collisions and hand visibility. Live acceptance must
also check the final composed image, book switching, menus and clicks at the
eighth history row. A successful callback test alone cannot establish visibility.
