# BKPOS Development Project

This is the MASTER PyCharm/source project.

## Development
Open this folder in PyCharm. Continue all source-code changes here.

## Release
Do not develop inside `dist` or a portable release folder. Those are generated
artifacts and are intentionally excluded from this clean development package.

## Database
Keep the live `pos_store.db` outside source control/release archives. Make a
verified backup before migrations or major changes.

## Build
Use the existing packaging/build scripts in the project when creating a
standalone Windows release.

## Project hygiene
Generated folders such as `build`, `dist`, and `__pycache__` are intentionally
not stored in this clean developer archive. PyCharm/PyInstaller recreates
them when required.
