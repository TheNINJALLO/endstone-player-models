"""
Player Models Plugin for Endstone.

Captures player skins and creates unique NPC entities for each player.
"""

import json
import threading
from datetime import datetime, time
from pathlib import Path
from typing import Optional, Set

from endstone.event import event_handler, PlayerJoinEvent, PlayerSkinChangeEvent
from endstone.plugin import Plugin

from endstone_player_models.addon_manager import AddonManager
from endstone_player_models.skin_processor import (
    is_3d_skin,
    sanitize_player_name,
    get_next_version,
    save_skin_texture,
)


class PlayerModelsPlugin(Plugin):
    """
    Endstone plugin that captures player skins and creates NPC entities.
    
    When a player joins or changes their skin:
    1. Validates the skin (skips 3D/custom skins)
    2. Creates a unique entity with ID based on player name
    3. Saves the skin texture
    4. Updates addon files
    
    Version bumping happens on a schedule (default: 11:30 AM EST) to prevent
    constant resource pack updates that disrupt player downloads.
    """
    
    prefix = "PlayerModels"
    api_version = "0.11"
    
    def __init__(self):
        super().__init__()
        self._settings: dict = {}
        self.addon_manager: Optional[AddonManager] = None
        self._processed_skins: Set[str] = set()  # Track processed skin IDs this session
        self._new_skins_added: bool = False  # Track if new skins were added since last version bump
        self._scheduler_thread: Optional[threading.Thread] = None
        self._scheduler_running: bool = False
    
    def on_load(self) -> None:
        """Called when the plugin is loaded."""
        self.logger.info("Player Models plugin loading...")
    
    def on_enable(self) -> None:
        """Called when the plugin is enabled."""
        self.logger.info("Player Models plugin enabling...")
        
        # Load configuration
        self._load_config()
        
        # Initialize addon manager
        addon_path = Path(__file__).parent / "player models addon"
        self.addon_manager = AddonManager(
            addon_path,
            namespace=self._settings.get("addon_namespace", "ninjos")
        )
        
        # Deploy addon files if they don't exist on the server
        self._ensure_addon_deployed()
        
        # Register event listeners
        self.register_events(self)
        
        # Start version bump scheduler
        self._start_scheduler()
        
        self.logger.info("Player Models plugin enabled!")
    
    def _start_scheduler(self):
        """Start the scheduled version bump thread."""
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        
        bump_hour = self._settings.get("version_bump_hour", 11)
        bump_minute = self._settings.get("version_bump_minute", 30)
        self.logger.info(f"Version bump scheduler started - will bump at {bump_hour:02d}:{bump_minute:02d}")
    
    def _scheduler_loop(self):
        """Background loop that checks if it's time to bump versions."""
        import time as time_module
        
        bump_hour = self._settings.get("version_bump_hour", 11)
        bump_minute = self._settings.get("version_bump_minute", 30)
        
        last_bump_date = None
        
        while self._scheduler_running:
            try:
                now = datetime.now()
                current_time = now.time()
                target_time = time(bump_hour, bump_minute)
                
                # Check if it's time to bump and we haven't bumped today
                if (current_time.hour == bump_hour and 
                    current_time.minute == bump_minute and
                    last_bump_date != now.date()):
                    
                    if self._new_skins_added:
                        self.logger.info("Scheduled version bump - new skins were added")
                        self._perform_version_bump()
                        self._new_skins_added = False
                        last_bump_date = now.date()
                    else:
                        self.logger.info("Scheduled version bump time reached - no new skins, skipping")
                        last_bump_date = now.date()
                
                # Sleep for 30 seconds before checking again
                time_module.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                time_module.sleep(60)
    
    def _perform_version_bump(self):
        """Perform the actual version bump."""
        try:
            new_version = self.addon_manager.bump_version()
            self.logger.info(f"Bumped addon version to {new_version}")
            
            # Update world pack files
            server_path = self._get_server_path()
            world_folder_name = self._get_world_folder_name()
            
            if server_path and world_folder_name:
                world_folder = server_path / "worlds" / world_folder_name
                self.addon_manager._update_world_packs(world_folder)
                self.logger.info(f"Updated world pack versions to {new_version}")
        except Exception as e:
            self.logger.error(f"Failed to bump version: {e}")
    
    def _ensure_addon_deployed(self):
        """Ensure the addon files are deployed to the server."""
        server_path = self._get_server_path()
        world_folder_name = self._get_world_folder_name()
        
        if not server_path or not world_folder_name:
            self.logger.warning("Server path or world folder not configured, skipping initial deployment")
            return
        
        # Check if behavior pack exists
        behavior_dest = server_path / "development_behavior_packs" / "player models Behavior"
        resource_dest = server_path / "worlds" / world_folder_name / "resource_packs" / "player models Resources"
        
        needs_deployment = not behavior_dest.exists() or not resource_dest.exists()
        
        if needs_deployment:
            self.logger.info("Addon not found on server, deploying initial files...")
            if self.addon_manager.deploy_to_world(server_path, world_folder_name, self.logger):
                self.logger.info("Initial addon deployment successful!")
            else:
                self.logger.error("Failed to deploy initial addon files")
        else:
            self.logger.info("Addon files already exist on server")
        
        # Set deployed paths so addon manager works with server files
        self.addon_manager.set_deployed_paths(server_path, world_folder_name)
        
        # Log current version
        try:
            current_version = self.addon_manager.get_current_version()
            self.logger.info(f"Current addon version: {current_version}")
        except Exception as e:
            self.logger.warning(f"Could not read addon version: {e}")
    
    def on_disable(self) -> None:
        """Called when the plugin is disabled."""
        self._scheduler_running = False
        
        # Perform final version bump if there are pending skins
        if self._new_skins_added:
            self.logger.info("Plugin disabling with pending skins - bumping version now")
            self._perform_version_bump()
        
        self.logger.info("Player Models plugin disabled.")
    
    def _load_config(self):
        """Load plugin configuration from config.json."""
        config_path = Path(__file__).parent / "config.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._settings = json.load(f)
                self.logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                self.logger.error(f"Failed to load config: {e}")
                self._use_default_config()
        else:
            self.logger.warning("Config file not found, using defaults")
            self._use_default_config()
    
    def _use_default_config(self):
        """Use default configuration values."""
        self._settings = {
            "server_path": "/home/container",
            "world_folder_name": "MyWorld",
            "skip_3d_skins": True,
            "enable_on_join": True,
            "enable_on_skin_change": True,
            "addon_namespace": "ninjos",
            "version_bump_hour": 11,
            "version_bump_minute": 30
        }
    
    def _get_server_path(self) -> Optional[Path]:
        """Get the server base path from configuration."""
        server_path = self._settings.get("server_path", "")
        if not server_path:
            return None
        return Path(server_path)
    
    def _get_world_folder_name(self) -> Optional[str]:
        """Get the world folder name from configuration."""
        return self._settings.get("world_folder_name", "")
    
    @event_handler
    def on_player_join(self, event: PlayerJoinEvent):
        """Handle player join event to capture their skin."""
        if not self._settings.get("enable_on_join", True):
            return
        
        player = event.player
        self._process_player_skin(player, is_skin_change=False)
    
    @event_handler
    def on_player_skin_change(self, event: PlayerSkinChangeEvent):
        """Handle skin change event to capture the new skin."""
        if not self._settings.get("enable_on_skin_change", True):
            return
        
        player = event.player
        new_skin = event.new_skin
        
        # Process with the new skin data
        self._process_player_skin(player, skin=new_skin, is_skin_change=True)
    
    def _process_player_skin(self, player, skin=None, is_skin_change: bool = False):
        """
        Process a player's skin and create entity files.
        
        Args:
            player: The player object
            skin: Optional skin object (for skin change events)
            is_skin_change: Whether this is a skin change (vs initial join)
        """
        try:
            self.logger.info(f"Processing skin for player: {player.name}")
            
            # Get skin data
            if skin is None:
                skin = player.skin
            
            if skin is None:
                self.logger.warning(f"No skin data available for player {player.name}")
                return
            
            self.logger.info(f"Skin ID: {skin.id}")
            
            # Get skin image
            skin_image = skin.image
            
            if skin_image is None:
                self.logger.warning(f"Skin image is None for player {player.name}")
                return
            
            # Log skin dimensions for debugging
            self.logger.info(f"Skin image shape: {skin_image.shape}")
            
            # Check for 3D/custom skins
            if self._settings.get("skip_3d_skins", True) and is_3d_skin(skin_image):
                self.logger.info(f"Skipping 3D/custom skin for {player.name} (dimensions: {skin_image.shape})")
                return
            
            # Create a unique skin identifier to avoid duplicate processing
            skin_id = f"{player.name}_{skin.id}"
            if skin_id in self._processed_skins and not is_skin_change:
                self.logger.info(f"Skin already processed for {player.name}")
                return
            
            # Sanitize player name for entity ID
            base_entity_id = sanitize_player_name(player.name)
            
            # Get existing entity IDs from the deployed addon
            existing_ids = self.addon_manager.get_existing_entity_ids()
            self.logger.info(f"Existing entity IDs: {existing_ids}")
            
            # Check if player entity already exists with texture
            if base_entity_id in existing_ids and not is_skin_change:
                # Verify the texture file actually exists
                texture_path = self.addon_manager.get_texture_path(base_entity_id)
                if texture_path.exists():
                    # Entity and texture exist, skip
                    self.logger.info(f"Entity for {player.name} already exists ({base_entity_id}), skipping")
                    self._processed_skins.add(skin_id)
                    return
                else:
                    # Entity ID found but texture missing - recreate
                    self.logger.info(f"Entity {base_entity_id} exists but texture missing, recreating")
            
            # For skin changes, create a new version
            if is_skin_change:
                entity_id = get_next_version(base_entity_id, existing_ids)
                self.logger.info(f"Skin change detected, creating new entity version: {entity_id}")
            else:
                entity_id = base_entity_id
                self.logger.info(f"Creating new entity: {entity_id}")
            
            # Save texture
            texture_path = self.addon_manager.get_texture_path(entity_id)
            if not save_skin_texture(skin_image, texture_path, self.logger):
                self.logger.error(f"Failed to save texture for {player.name}")
                return
            
            # Create entity files
            display_name = player.name
            if is_skin_change and entity_id != base_entity_id:
                # Extract version number
                version_num = entity_id[len(base_entity_id):]
                display_name = f"{player.name} (v{version_num})"
            
            if not self.addon_manager.create_entity_files(entity_id, display_name, self.logger):
                self.logger.error(f"Failed to create entity files for {player.name}")
                return
            
            # Mark that new skins were added (version bump will happen at scheduled time)
            self._new_skins_added = True
            self.logger.info(f"New skin added - version bump pending (will occur at scheduled time)")
            
            # Mark as processed
            self._processed_skins.add(skin_id)
            
            namespace = self._settings.get("addon_namespace", "ninjos")
            self.logger.info(
                f"Created entity {namespace}:{entity_id} for player {player.name}"
            )
            
        except Exception as e:
            self.logger.error(f"Error processing skin for {player.name}: {e}")

