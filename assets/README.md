# Asset Policy

Runtime assets that the game imports at runtime live under `src/rts_nano/assets`
so they are packaged with the Python project.

Source and development art lives under `assets/development`. Files in this area
may include `.xcf`, `.jpg`, large reference images, and work-in-progress PNGs.
They are not imported by runtime code. Export optimized runtime sprites and
portraits into `src/rts_nano/assets/sprites` or `src/rts_nano/assets/portraits`.

Before adding new source art, use descriptive filenames and avoid accidental
copy names. Large source files should move to Git LFS if they become costly to
store in normal Git history.
