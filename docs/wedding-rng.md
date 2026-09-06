# Wedding announcement and replay RNG

The chapel, church and cathedral information panel chooses a couple for its
monthly wedding announcement while rendering the panel. This consumes the same
RNG1 state used by the simulation. Opening that panel is not a timed gameplay
command, so command playback does not reproduce the two advances. Spectators
can also introduce them by inspecting a church during playback.

The 0.27.0 fix gates just those two RNG calls during active single-player
recording/playback. Candidate scanning, previously displayed couple exclusion,
announcement history and native rendering remain. Selection uses the current
RNG value for both names, so presentation variety may change. Unit data is not
modified by the selector. The existing scope gates preserve vanilla behavior
when recorder is idle and in multiplayer.

## Native evidence

The read-only OpenSHC Ghidra database identifies the only direct caller of
`UnitsState::chooseHusbandAndWife` as
`UI::Rendering::RenderBuildingMenu_ChapelAndChurch`. The renderer checks that
the selected religious building has an employee and that the month differs
from its cached display month before calling the selector. The selector
collects up to 100 eligible men and women, consumes RNG1 after choosing each,
and writes only output IDs and its presentation history.

| Site | Crusader 1.41 | Extreme 1.41 |
| --- | --- | --- |
| Renderer call to selector | `43C2E3` | `43C523` |
| Selector entry | `539DF0` | `53A210` |
| First RNG1 call | `539EAB` | `53A2CB` |
| Second RNG1 call | `539EC6` | `53A2E6` |

`tests/check_wedding_native.py`, run by `tests/check_executables.py`, executes
the complete original selector and RNG routine on both executables. It checks
return values, eligible outputs, history, preserved registers and stack, and
all non-stack writes. Cases include missing candidates, repeated visits,
populations exceeding the 100-entry candidate limit, index wrap, both active
SP modes and unchanged idle/multiplayer behavior. The native renderer's call
target and both complete RNG call instructions are checked as well.

## Reproduction and limits

Published 0.26.0 replay `20260906-194951-0001` diverged at checkpoint 47,104
twice, including playback without changing speed. Expected RNG state was
`[32129,9380,7922,7862]`; playback had `[15593,9380,7922,7860]`.
The previous checkpoint at 47,040 matched. The two extra RNG1 advances are
consistent with this panel's selector, but the original recording has no
per-call attribution or panel-visit history proving that specific cause.
AI Bink/thanks functions inspected along the nearby goods-transfer command
contained no direct RNG advances; that is not a complete audit of their callees.

This is a proven missing source of presentation RNG, not a claim that every
replay desync is solved. A fresh capture/playback comparison is still required:
open a staffed chapel/church with eligible workers, let the month change with
the panel open, inspect it while paused, and repeat playback with different
inspection, speed and pause choices. Verify completion through the final tick,
including allied commands and Automarket. Repeat on Extreme.

New captures use `recorder-sp-v10`. A failed older capture cannot be repaired
reliably by inserting two guessed random advances: it lacks the exact timing
and menu history. The module rejects the older simulation profile before load.
Further requested UI and multiplayer work is tracked in [the roadmap](roadmap.md).
