# Changelog

## Nov 11, 2023
Polish and merge work from April of this year:
- adopt flake.nix and catch up to recent nixpkgs-unstable
- ~track test breaks from 1.8.20->pre-1.9.7
  
  doxy_db's test suite builds sqlite3 output for (most of) doxygen's collection of examples (which I'm using because there isn't a canonical corpus that exercises all doxygen features yet), runs it through doxy_db, and then asserts a lot of output/data-structure details.

  Useful for spotting bugs and behavior shifts in Doxygen and the sqlite3 output, but this also means it needs updating when shifts arise. Hopefully we can settle into less-fragile assertions over time, but these are informative enough that I'm not in a hurry.

  Preserving my working notes from these fixes:
  - between 1.8.20 and 1.9.0
    - there's at least one new space (looks like a correct fix?) in TestManual.test_doc_search; unclear from checking the log between revs what caused; would have to bisect
          
      just manually fixing up tests for now

  - 1.9.0 -> 1.9.1
    - example and page now have location
    - bug now has file
  - 1.9.1 -> 1.9.2
    - this is where the schema_version stops working
    - between 6a7201851a1667da40b4e2a1cf7b481c2d386803 and 5d0281a264e33ec3477bd7f6a9dcef79a6ef8eeb a number of test breaks creep in that I have fixes for, but the schema version isn't broke yet
    - with fix commit, schema_version works; need to upstream it
  - 1.9.2 -> 1.9.3: 
    - minor test fixes
  - 1.9.3 -> 1.9.4 -> 1.9.5 -> 1.9.6 -> 1.9.7 -> 1.9.8: no test breaks

- upstream fixes for regressions discovered via above
- cut back on doxygen overrides in the Nix expressions after a successful effort to enable the experimental sqlite3 support by default in Nixpkgs

## August 26, 2020
Update to target upstream doxygen release 1.8.20.

## May 9, 2020
Switch to target upstream doxygen after merge of fix developed below (a specific post 1.8.19 commit).

## May 4, 2020
Update doxygen target from my fork's 1.8.15-equivalent to its 1.8.19 equivalent.

(The sqlite3 output isn't fully supported yet; there've been some false starts with regressions that rendered this behavior in unstream unusable without fixes.)

## August 13, 2018
Publish first working draft
