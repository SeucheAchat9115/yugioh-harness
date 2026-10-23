# Get a new replay through the browser inspector

Supply the **native replay JSON response**, its Duelingbook replay URL and the
format played. HTML saved from the page and copied Chat/Duel/Game text are not
supported replay inputs. Repeat the following for each match.

## Copy the replay response

1. Open the replay in Duelingbook and complete any normal browser verification.
2. Open developer tools with **F12** or **Ctrl+Shift+I** (Mac:
   **Cmd+Option+I**). Select **Network**, then **Fetch/XHR**.
3. Reload the replay with Network open. Filter requests for `replay` or
   `view-replay`. Select the request whose **Response** contains the replay data.
   The Elements/Inspector tab shows page HTML, not this JSON.
4. Check the response is a JSON object containing `plays`, `player1`, `player2`
   and `id`. `plays` should be an array of actions such as `Pick first`,
   `Draw card` and `Start turn`, rather than an error or verification page.
   The numeric `id` must match the duel portion of the URL: for
   `replay?id=40753-85958923`, it is `85958923`.
5. Right-click the request and select **Copy → Copy response** (the wording
   varies by browser), or copy the complete raw Response. Save it as a UTF-8
   file such as `match.json`. Copy the whole response, not only selected plays,
   a formatted preview subtree or the visible current turn.
6. Supply that file alongside the replay URL, export date, played format and any
   known rules/banlist/card-text references. Keep one complete match per file,
   including later games and sideboarding.

If you cannot find the response, clear the filter, select **All** and reload.
Some browser/app versions may deliver data through a **WS** connection instead;
inspect its Messages/Frames for the replay response. A message wrapper is not
necessarily the supported export: the importer expects the complete object with
`plays` and both player objects. A copied HTML page or an empty Network list
cannot substitute for replay data.

Copy only response data. Do not supply HAR files, Copy as cURL output, request
headers, cookies or browser verification tokens. You do not need to enter a
command in the Console. The importer uses your supplied file offline; it does
not fetch protected replay endpoints.

## Check what the export contains

- **Player identities and whole match:** both `player1.username` and
  `player2.username`, all source plays and later games.
- **Hidden information:** inspect `conceal` and `plays[*].log[*].private_log`.
  Our selected unconcealed export includes named draws for both players.
  If yours conceals names, report that limitation; changing `conceal` does not
  recover missing cards. Only use data the normal replay view permits you to see.
- **Card definitions:** `plays[*].card` or `plays[*].cards` may contain `name`,
  `effect` and `serial_number`. The latter is the passcode used for external
  [card reference lookup](card-metadata.md). An action/card `id` or `object_id`
  is not interchangeable with a passcode.
- **Format:** Duelingbook may say Unlimited (`format: "uu"`, `rules: "*"`) even
  for a historical-format match. State the actual format separately. Do not
  change those literal source fields to make the replay look verified.

Not every export includes every field. Keep unknown cards, missing timestamps,
manual corrections, chat and connection events as recorded. Do not fill gaps.
Main/Extra/Side arrays of runtime IDs are not complete named decklists. For a
full-game scored evaluation, also provide available named decklists and the
historical rules, banlist and card-text version. Reviewed states, information
visibility and decision windows are still required after importing.

The whole export can reveal opponent hands and future cards. It is evaluator
source data, never a prompt for the playing agent.

## Import and inspect

An orchestrator can perform these steps internally when you supply a replay;
duel players do not need to run Python. Maintainer commands:

```sh
# Use the actual URL and response retrieval timestamp for your match.
yugioh-benchmark convert-json imports/match.json --source https://www.duelingbook.com/replay?id=40753-85958923 --retrieved-at 2026-10-08T00:00:00Z --output replays/my-match
yugioh-benchmark inspect replays/my-match
yugioh-benchmark candidates replays/my-match
```

Importing rejects mismatched URL/duel IDs, malformed JSON, duplicate keys, tag
duels and an existing output folder. Each native play keeps its source index and
gets a hashed event file. Inspect the manifest's `source_metadata.audit` for
named-draw coverage and LP evidence; candidates are unreviewed work items.
See [native JSON coverage and provenance](native-json.md).

Keep original unselected exports in ignored `imports/`. Deliberately version a
selected gameplay fixture after account/display metadata removal, its bundle,
candidate index, attribution, hashes and known gaps in the source registry.
External card references remain dated snapshots, separate from the source and
historical legality review. Old text/API-observation bundles are unsupported;
reimport the native response and review cases against its native ID and digest.
