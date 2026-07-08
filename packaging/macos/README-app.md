# macOS Standard App package

Use the DMG package for new installs. Drag iLab GPT CONJURE.app to Applications,
then launch it from Finder or Spotlight.

This app stores user data in:

```text
~/Library/Application Support/iLab GPT CONJURE
```

On first launch, the app can detect adjacent legacy portable data and asks
before copying it into the standard app data directory. Migration copies portable
data only; it does not move or delete the old `data/` folder, and it will not
overwrite an existing standard data directory.

The app is not notarized. If Gatekeeper blocks first launch, right-click
or Control-click iLab GPT CONJURE.app, choose Open, and confirm the system
prompt.

The standard app checks for updates by opening the GitHub Release page. Automatic
self-replacement is intentionally limited to portable packages.
