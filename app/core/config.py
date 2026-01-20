import os
import json
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Dict, Any

class Settings(BaseSettings):
    # --- Paths ---
    # We define BASE_DIR as a field so it can be accessed via settings.BASE_DIR
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # --- Env Vars ---
    PROJECT_NAME: str = "Access Afya Vetting Agent"
    ENVIRONMENT: str = "development"
    SUPABASE_URL: str = "http://127.0.0.1:54321"
    SUPABASE_KEY: str = ""
    OPENAI_API_KEY: str = ""
    
    # --- JSON Configs (Loaded on init) ---
    RULES_CONFIG: Dict[str, Any] = {}
    STATE_MACHINE: Dict[str, Any] = {}
    TERRITORIES: Dict[str, Any] = {}
    SYSTEM_PROMPT: str = ""

    def load_configs(self):
        """Loads external JSON/MD files into memory settings."""
        config_dir = self.BASE_DIR / "config"
        
        # Load Rules Engine
        with open(config_dir / "rules_engine.json", "r") as f:
            self.RULES_CONFIG = json.load(f)
            
        # Load State Machine
        with open(config_dir / "state_machine.json", "r") as f:
            self.STATE_MACHINE = json.load(f)
            
        # Load Territories
        with open(config_dir / "territories.json", "r") as f:
            self.TERRITORIES = json.load(f)
            
        # Load System Prompt
        with open(config_dir / "system_prompt.md", "r") as f:
            self.SYSTEM_PROMPT = f.read()

    class Config:
        env_file = ".env"
        # This is required to allow Path objects in Pydantic models
        arbitrary_types_allowed = True

# Singleton Instance
settings = Settings()
settings.load_configs()