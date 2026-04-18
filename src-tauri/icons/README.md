# Icons

Placeholder directory. Tauri's bundler reads the icon set listed in
`tauri.conf.json::bundle.icon`. Generate a full icon set from a single
source PNG (1024×1024 recommended) with:

```
cd src-tauri && npx @tauri-apps/cli@2 icon path/to/app-icon.png
```

The CLI writes `32x32.png`, `128x128.png`, `128x128@2x.png`,
`icon.icns` (macOS), and `icon.ico` (Windows) into this directory.

Until that's done, `cargo tauri build` will fail with a "can't find
icon" error. `cargo tauri dev` runs fine without icons.
