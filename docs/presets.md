# Confirmed preset catalogue

## Reno — Restore Train Dialogue

ID: `reno-restore-train-dialogue`.
Observed problem: after the completed kibble transaction, Reno's entry reaches Goodbye instead of his ordinary dialogue hub.
The ordinary hub contains the model-train handover option.

The preset changes **only** `reno.HasRenoAskedForKibble: true → false`.
It requires the tested completed-deal flags, papers state, successful train repair, a model train in inventory,
a completed Reno greeting, known missing train and no completed train handover.
See the data descriptor in `src/zero_parades_savelab/data/presets.json` for the complete checked conditions.

It preserves `reno.GotKibble`, `king_of_trade.BoughtKibble`, `reno.GivesYouUVsExitPapers`
and `reno.AlternateGoodByeAtEnd`, inventory, tasks and all other state.
Clearing only `AlternateGoodByeAtEnd` is deliberately **not** offered: it can return to the kibble scene.
Coordinates and NPC snapshots are not changed.

This temporarily changes a historical global flag, so other conditional conversation lines can be affected.
Use the ordinary in-game handover, create a NEW manual save and finish with the next preset.

## Reno — Restore Historical Flag

ID: `reno-restore-historical-flag`.
On a new post-handover save only, changes `reno.HasRenoAskedForKibble: false → true`.
Requires `reno.ReturnedHisModelTrain = true`, the completed deal/papers flags and no model train in inventory.
Preserves the actual handover, inventory removal, rewards and progress created by the game.
Reno may return to Goodbye afterward. The goal is a completed train handover with the original historical request flag restored.

## Evidence and recovery

Both stages were verified through an actual local game session on 1.1 / 40781:
Reno accepted the repaired train through dialogue, the train disappeared normally, papers and progress remained,
and the temporary flag was subsequently restored. This is evidence for that story configuration, not every possible playthrough.

Exported copies and original replacements have separate verified backups.
To undo the first stage, restore its backup. To undo only the second stage, restore the NEW post-handover backup,
which already contains the successful handover. Do not roll the entire folder back to a pre-handover snapshot.

## Adding descriptors

Presets are JSON data, not executable plugins. A descriptor declares `id`, `title`, `description`, `evidence`, `risk`,
`conditions` and `changes`. Supported conditions are boolean `flag` checks and `item` presence checks;
changes are explicit existing-boolean transitions with before/after values. `card_unread` can additionally verify that a tested dialogue card has not been read. Missing prerequisites block the preset.

The registry can load additional descriptor files through its Python API without changes to the codec.
Adding a bundled preset requires synthetic condition tests, a precise diff, in-game evidence and a recovery plan.
Unsupported predicates or arbitrary code in descriptors are rejected. Unverified story assumptions must not be labelled Confirmed.
