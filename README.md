# Endstone Player Models

An Endstone plugin that captures player skins and creates unique NPC entities for each player.

## Features

- **Automatic Skin Capture**: Captures player skins when they join or change their skin
- **Unique Entity IDs**: Creates entities with player-based identifiers (e.g., `ninjos:playername`)
- **Skin Change Versioning**: Tracks skin changes with versioned entities (`ninjos:playername2`, etc.)
- **3D Skin Detection**: Skips 128x128 custom skins that don't fit the standard player model
- **Auto-Deployment**: Automatically deploys addon files to the server on plugin load

## Configuration

Edit `config.json`:

```json
{
    "server_path": "/home/container",
    "world_folder_name": "MyWorld",
    "skip_3d_skins": true,
    "enable_on_join": true,
    "enable_on_skin_change": true,
    "addon_namespace": "ninjos"
}
```

## Usage

After a player joins, spawn their NPC using:

```
/summon ninjos:playername
```

## Installation

1. Build the plugin: `pip install build && python -m build`
2. Install the wheel in your Endstone plugins folder
3. Configure `config.json` with your world folder name
4. Start the server

## License

MIT
