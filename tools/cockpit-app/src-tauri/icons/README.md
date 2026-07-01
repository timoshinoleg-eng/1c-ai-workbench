# Tauri icons

Tauri 2.x requires platform-specific icon files referenced from
`tauri.conf.json` → `bundle.icon`:

```
icons/
├── 32x32.png
├── 128x128.png
├── 128x128@2x.png
├── icon.icns       (macOS)
└── icon.ico        (Windows)
```

## How to generate them

These files are NOT committed to the repository by design — they are
binary blobs that the build pipeline produces. To scaffold a release
build locally, run the Tauri CLI icon generator against a single
square source image (1024×1024 PNG recommended):

```powershell
cd tools\cockpit-app
npm install
npx tauri icon .\public\tauri.svg
```

The CLI will populate this directory with the required sizes.

For the v0.1.0 scaffold you can ship an empty `tauri.svg` placeholder;
the `tauri build` command will only fail at the `bundle.icon` step
until the real icons are present. `tauri dev` works without icons.
