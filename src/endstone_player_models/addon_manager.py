"""
Addon management utilities for Player Models plugin.

Handles creating entity files, updating manifests, and deploying to world folders.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set


class AddonManager:
    """Manages the player models addon files."""
    
    def __init__(self, addon_path: Path, namespace: str = "ninjos"):
        """
        Initialize the addon manager.
        
        Args:
            addon_path: Path to the addon folder containing behavior and resource packs
            namespace: The entity namespace (e.g., "ninjos")
        """
        self.addon_path = addon_path
        self.namespace = namespace
        
        # Paths to bundled template pack folders
        self.behavior_pack = addon_path / "player models Behavior"
        self.resource_pack = addon_path / "player models Resources"
        
        # Deployed paths (set after calling set_deployed_paths)
        self._deployed_behavior: Optional[Path] = None
        self._deployed_resource: Optional[Path] = None
        
        # Important file paths (relative to resource pack)
        self._update_paths()
        
        # Template files
        self.behavior_template = self.behavior_entities / "playermodel.behavior.json"
        self.entity_template = self.resource_entities / "playermodel.entity.json"
    
    def _update_paths(self):
        """Update derived paths based on current pack locations."""
        self.behavior_entities = self.behavior_pack / "entities"
        self.resource_entities = self.resource_pack / "entity"
        self.textures_folder = self.resource_pack / "textures" / "entity"
        self.lang_file = self.resource_pack / "texts" / "en_US.lang"
    
    def set_deployed_paths(self, server_path: Path, world_folder_name: str):
        """
        Set the deployed addon paths for working with server files.
        
        After calling this, all operations work on the deployed addon.
        
        Args:
            server_path: Base server path (/home/container)
            world_folder_name: World folder name
        """
        self._deployed_behavior = server_path / "development_behavior_packs" / "player models Behavior"
        self._deployed_resource = server_path / "worlds" / world_folder_name / "resource_packs" / "player models Resources"
        
        # Switch to deployed paths if they exist
        if self._deployed_resource.exists():
            self.resource_pack = self._deployed_resource
            self._update_paths()
        
        if self._deployed_behavior.exists():
            self.behavior_pack = self._deployed_behavior
            self.behavior_entities = self.behavior_pack / "entities"
    
    def get_existing_entity_ids(self) -> Set[str]:
        """
        Scan for existing player entity IDs in the addon.
        
        Returns:
            Set of entity IDs (without namespace) that already exist
        """
        existing_ids = set()
        
        # Scan deployed resource pack entities (if available)
        search_path = self.resource_entities
        if self._deployed_resource and self._deployed_resource.exists():
            search_path = self._deployed_resource / "entity"
        
        if search_path.exists():
            for entity_file in search_path.glob("*.entity.json"):
                # Extract entity ID from filename
                entity_id = entity_file.stem.replace(".entity", "")
                if entity_id != "playermodel":  # Exclude template
                    existing_ids.add(entity_id)
        
        return existing_ids
    
    def entity_exists(self, entity_id: str) -> bool:
        """
        Check if an entity already exists.
        
        Args:
            entity_id: The entity ID to check
            
        Returns:
            True if entity files exist
        """
        # Check deployed resource pack
        resource_path = self.resource_entities / f"{entity_id}.entity.json"
        behavior_path = self.behavior_entities / f"{entity_id}.behavior.json"
        
        return resource_path.exists() or behavior_path.exists()
    
    def create_entity_files(
        self, 
        entity_id: str, 
        display_name: str,
        logger=None
    ) -> bool:
        """
        Create behavior and resource entity files for a player.
        
        Args:
            entity_id: The entity ID (sanitized player name, e.g., "then1nj4ll0")
            display_name: The player's display name for language file
            logger: Optional logger for debug output
            
        Returns:
            True if successful
        """
        try:
            # Skip if already exists
            if self.entity_exists(entity_id):
                if logger:
                    logger.info(f"Entity {entity_id} already exists, skipping creation")
                return True
            
            # Create resource pack entity file
            self._create_resource_entity(entity_id)
            
            # Create behavior pack entity file
            self._create_behavior_entity(entity_id)
            
            # Update language file
            self._update_language_file(entity_id, display_name)
            
            if logger:
                logger.info(f"Created entity files for {self.namespace}:{entity_id}")
            
            return True
            
        except Exception as e:
            if logger:
                logger.error(f"Failed to create entity files: {e}")
            return False
    
    def _create_resource_entity(self, entity_id: str):
        """Create the resource pack entity JSON file."""
        # Load template from bundled addon
        template_path = self.addon_path / "player models Resources" / "entity" / "playermodel.entity.json"
        with open(template_path, 'r', encoding='utf-8') as f:
            template = json.load(f)
        
        # Modify for this player
        desc = template["minecraft:client_entity"]["description"]
        
        # Update identifier
        desc["identifier"] = f"{self.namespace}:{entity_id}"
        
        # Update texture path
        desc["textures"]["default"] = f"textures/entity/{entity_id}"
        
        # Ensure output directory exists
        self.resource_entities.mkdir(parents=True, exist_ok=True)
        
        # Save new entity file
        output_path = self.resource_entities / f"{entity_id}.entity.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent='\t')
    
    def _create_behavior_entity(self, entity_id: str):
        """Create the behavior pack entity JSON file."""
        # Load template from bundled addon
        template_path = self.addon_path / "player models Behavior" / "entities" / "playermodel.behavior.json"
        with open(template_path, 'r', encoding='utf-8') as f:
            template = json.load(f)
        
        # Modify for this player
        desc = template["minecraft:entity"]["description"]
        
        # Update identifier
        desc["identifier"] = f"{self.namespace}:{entity_id}"
        
        # Ensure output directory exists
        self.behavior_entities.mkdir(parents=True, exist_ok=True)
        
        # Save new entity file
        output_path = self.behavior_entities / f"{entity_id}.behavior.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent='\t')
    
    def _update_language_file(self, entity_id: str, display_name: str):
        """Add entity name entries to the language file."""
        full_id = f"{self.namespace}:{entity_id}"
        
        # Read existing content
        existing_lines = []
        if self.lang_file.exists():
            with open(self.lang_file, 'r', encoding='utf-8') as f:
                existing_lines = f.readlines()
        
        # Check if entries already exist
        entity_key = f"entity.{full_id}.name="
        spawn_key = f"item.spawn_egg.entity.{full_id}.name="
        
        has_entity = any(entity_key in line for line in existing_lines)
        has_spawn = any(spawn_key in line for line in existing_lines)
        
        # Add new entries
        new_lines = []
        if not has_entity:
            new_lines.append(f"entity.{full_id}.name={display_name}\n")
        if not has_spawn:
            new_lines.append(f"item.spawn_egg.entity.{full_id}.name=Spawn {display_name}\n")
        
        if new_lines:
            # Ensure parent directory exists
            self.lang_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.lang_file, 'a', encoding='utf-8') as f:
                f.writelines(new_lines)
    
    def bump_version(self) -> List[int]:
        """
        Increment version numbers in both pack manifests.
        
        Returns:
            The new version as [major, minor, patch]
        """
        # Bump resource pack manifest
        resource_manifest = self.resource_pack / "manifest.json"
        new_version = self._bump_manifest_version(resource_manifest)
        
        # Bump behavior pack manifest and update dependency version
        behavior_manifest = self.behavior_pack / "manifest.json"
        self._bump_manifest_version(behavior_manifest, dependency_version=new_version)
        
        return new_version
    
    def _bump_manifest_version(
        self, 
        manifest_path: Path, 
        dependency_version: Optional[List[int]] = None
    ) -> List[int]:
        """
        Bump the version in a manifest file.
        
        Args:
            manifest_path: Path to the manifest.json
            dependency_version: If provided, also update dependency versions
            
        Returns:
            The new version
        """
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        # Get current version and increment patch
        version = manifest["header"]["version"]
        version[2] += 1  # Increment patch version
        
        # Update module versions
        for module in manifest.get("modules", []):
            module["version"] = version.copy()
        
        # Update dependency versions if provided
        if dependency_version:
            for dep in manifest.get("dependencies", []):
                dep["version"] = dependency_version.copy()
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent='\t')
        
        return version
    
    def get_current_version(self) -> List[int]:
        """Get the current version from the resource pack manifest."""
        resource_manifest = self.resource_pack / "manifest.json"
        with open(resource_manifest, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        return manifest["header"]["version"]
    
    def get_pack_uuids(self) -> Dict[str, str]:
        """Get the UUIDs of both packs."""
        uuids = {}
        
        resource_manifest = self.resource_pack / "manifest.json"
        with open(resource_manifest, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            uuids["resource"] = manifest["header"]["uuid"]
        
        behavior_manifest = self.behavior_pack / "manifest.json"
        with open(behavior_manifest, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            uuids["behavior"] = manifest["header"]["uuid"]
        
        return uuids
    
    def deploy_to_world(
        self, 
        server_path: Path, 
        world_folder_name: str, 
        logger=None
    ) -> bool:
        """
        Deploy the addon to the server.
        
        Behavior pack goes to: {server_path}/development_behavior_packs/
        Resource pack goes to: {server_path}/worlds/{world_folder_name}/resource_packs/
        
        Args:
            server_path: Base server path (e.g., /home/container)
            world_folder_name: Name of the world folder (e.g., MyWorld)
            logger: Optional logger
            
        Returns:
            True if successful
        """
        try:
            # Source paths - always use bundled addon template
            bundled_resource = self.addon_path / "player models Resources"
            bundled_behavior = self.addon_path / "player models Behavior"
            
            # Destination paths on server
            behavior_dest = server_path / "development_behavior_packs" / "player models Behavior"
            resource_dest = server_path / "worlds" / world_folder_name / "resource_packs" / "player models Resources"
            world_folder = server_path / "worlds" / world_folder_name
            
            # Ensure world folder exists
            if not world_folder.exists():
                if logger:
                    logger.error(f"World folder does not exist: {world_folder}")
                return False
            
            # Ensure parent directories exist
            behavior_dest.parent.mkdir(parents=True, exist_ok=True)
            resource_dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy resource pack from bundled template
            if resource_dest.exists():
                shutil.rmtree(resource_dest)
            shutil.copytree(bundled_resource, resource_dest)
            
            # Copy behavior pack from bundled template
            if behavior_dest.exists():
                shutil.rmtree(behavior_dest)
            shutil.copytree(bundled_behavior, behavior_dest)
            
            # Update world pack files (use bundled manifest for UUIDs)
            self._update_world_packs_from_bundled(world_folder, bundled_resource, bundled_behavior)
            
            if logger:
                logger.info(f"Deployed resource pack to {resource_dest}")
                logger.info(f"Deployed behavior pack to {behavior_dest}")
            
            return True
            
        except Exception as e:
            if logger:
                logger.error(f"Failed to deploy addon: {e}")
            return False
    
    def _update_world_packs(self, world_folder: Path):
        """Update world_resource_packs.json and world_behavior_packs.json."""
        uuids = self.get_pack_uuids()
        version = self.get_current_version()
        
        # Update resource packs
        resource_packs_file = world_folder / "world_resource_packs.json"
        self._update_pack_file(resource_packs_file, uuids["resource"], version)
        
        # Update behavior packs
        behavior_packs_file = world_folder / "world_behavior_packs.json"
        self._update_pack_file(behavior_packs_file, uuids["behavior"], version)
    
    def _update_world_packs_from_bundled(
        self, 
        world_folder: Path, 
        bundled_resource: Path,
        bundled_behavior: Path
    ):
        """Update world pack files using bundled template manifests."""
        # Get UUIDs from bundled templates
        uuids = {}
        
        resource_manifest = bundled_resource / "manifest.json"
        with open(resource_manifest, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            uuids["resource"] = manifest["header"]["uuid"]
            version = manifest["header"]["version"]
        
        behavior_manifest = bundled_behavior / "manifest.json"
        with open(behavior_manifest, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
            uuids["behavior"] = manifest["header"]["uuid"]
        
        # Update resource packs
        resource_packs_file = world_folder / "world_resource_packs.json"
        self._update_pack_file(resource_packs_file, uuids["resource"], version)
        
        # Update behavior packs
        behavior_packs_file = world_folder / "world_behavior_packs.json"
        self._update_pack_file(behavior_packs_file, uuids["behavior"], version)
    
    def _update_pack_file(self, pack_file: Path, pack_id: str, version: List[int]):
        """Update or create a world pack file."""
        packs = []
        
        # Load existing packs if file exists
        if pack_file.exists():
            with open(pack_file, 'r', encoding='utf-8') as f:
                try:
                    packs = json.load(f)
                except json.JSONDecodeError:
                    packs = []
        
        # Find and update or add our pack
        found = False
        for pack in packs:
            if pack.get("pack_id") == pack_id:
                pack["version"] = version
                found = True
                break
        
        if not found:
            packs.append({
                "pack_id": pack_id,
                "version": version
            })
        
        # Save updated packs
        with open(pack_file, 'w', encoding='utf-8') as f:
            json.dump(packs, f, indent='\t')
    
    def get_texture_path(self, entity_id: str) -> Path:
        """Get the path where a player's texture should be saved."""
        # Ensure textures folder exists
        self.textures_folder.mkdir(parents=True, exist_ok=True)
        return self.textures_folder / f"{entity_id}.png"
