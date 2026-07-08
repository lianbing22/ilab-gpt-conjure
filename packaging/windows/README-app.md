# Windows Standard App ZIP

This is not an installer. Extract the ZIP to a normal user-writable folder and
double-click `iLab GPT CONJURE.exe`.

The standard app stores user data in:

```text
%APPDATA%\iLab GPT CONJURE
```

On first launch, the app can detect adjacent legacy portable data and asks
before copying it into the standard app data directory. Migration copies portable
data only; it does not move or delete the old `data\` folder, and it will not
overwrite an existing standard data directory.

The standard app checks for updates by opening the GitHub Release page. Automatic
self-replacement is intentionally limited to portable packages.
