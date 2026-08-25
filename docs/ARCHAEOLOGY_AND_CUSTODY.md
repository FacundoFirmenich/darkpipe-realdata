# Archaeology and evidence custody

## Native conversation

- Source: chatgpt-conversation://6a22c10e-05a0-838c-9689-3f075d570529
- Exact bounded read: 59 pages/turns to EOF; 492,585 characters.
- Every page has a cursor chain and SHA-256 receipt in evidence/native_thread_trace_manifest.json.
- One old, large CFL manuscript message on page 57 was truncated by transport. It is outside the governing DarkPipe branch. The missing tail was not reconstructed or invented.

## Current notebook snapshots

The ten available notebooks were read as notebook JSON, all cells included, and hashed. The most relevant patterns are GeOSync.realdata.ipynb, geo2.maso.ipynb and Untitled33.ipynb. The latter contains stored syntax errors in two cells; this finding is restricted to that snapshot and is not promoted into a claim about newer branches. The Fermi, Yukawa/GraviTools, Eduscience and plotting notebooks are adjacent or side branches.

See evidence/notebook_inventory.json for exact names, byte counts, hashes and classification.

## Adjacent Zenodo records

Metadata for records 19194518, 18480821, 17875888, 17548048 and 20102651 was verified through Zenodo's official API. Only the three small packages were downloaded for bounded inspection; the 640 MB SFA archive and 23 MB KwanTube archive were not downloaded. This avoided unnecessary local-disk use.

The inspected SFA and OpenADS packages are GPL-licensed. DarkPipe 0.3.0 is an original clean-room implementation; it does not copy GPL source. The scale-dependent-spacetime package was used only as contextual evidence.

## Historical package boundary

The old darkpipe_realdata_v02 ZIP is no longer accessible. Claims about its four passing smoke tests remain historical statements from the native chat, not current verification. Version 0.3.0 was rebuilt from the native objective and current source contracts, then tested anew.

## Live adapter receipts

The default NOAA RTSW plus USGS run completed with 1,433 aligned real observations. INTERMAGNET HAPI was separately verified on 60 BOU observations after correcting the provider contract to combine /info metadata with /data rows. Both successful receipts and the preceding abstentions are retained under evidence/.
