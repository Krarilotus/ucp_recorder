# Report navigation while viewing a frozen replay

The original main-button action handler (`444B80` in SHC, `444DB0` in Extreme)
first separates report actions 71 through 79 from building and other controls.
It then rejects network-busy state and logical pause before entering report UI
preparation. SHC's pause comparison is at `444EB3`; Extreme's is at `4450E3`.
This is an existing native UI rule, not evidence of a simulation desync.

A completed replay deliberately keeps its simulation paused. Consequently the
native book click was ignored, even though selecting a portrait correctly changed
the rendered summary. The replay patch supplies equality flags at this one pause
comparison, only after playback restoration is active in a local session. It does
not clear the pause flag, alter player identity, bypass network-busy state, admit
building actions, or release command/tick guards. Outside replay the original
comparison executes unchanged. The existing native report transition still owns
the book and its tabs; scoped renderers own the selected player's displayed data.

`check_report_pause_native.py` executes the original admission branch with the
production trampoline in both variants: report/non-report actions, paused/running,
ordinary/offline multiplayer, inactive/active replay, and network-busy state.
These checks prove branch admission and preserved pause/register/stack state.
They do not replace in-game inspection of the resulting book and its controls.
