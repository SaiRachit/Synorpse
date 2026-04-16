"""
State Persistence - Save and restore system state
Allows resuming after restart with active goals and tasks
"""
import json
import pickle
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger("persistence")


class StatePersistence:
    """Handle state persistence and restoration"""
    
    def __init__(self, state_dir: str = "state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.state_file = self.state_dir / "system_state.json"
        self.checkpoint_dir = self.state_dir / "checkpoints"
        self.checkpoint_dir.mkdir(exist_ok=True)
    
    def save_state(self, state_data: Dict[str, Any]) -> bool:
        """
        Save current system state
        
        Args:
            state_data: Dictionary containing state to save
        
        Returns:
            True if successful
        """
        try:
            # Add metadata
            state_data["_metadata"] = {
                "saved_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            # Save to file
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2, default=str)
            
            logger.info(f"State saved to {self.state_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}", exc_info=True)
            return False
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """
        Load saved system state
        
        Returns:
            State dictionary or None if no saved state
        """
        try:
            if not self.state_file.exists():
                logger.info("No saved state found")
                return None
            
            with open(self.state_file, 'r') as f:
                state_data = json.load(f)
            
            logger.info(f"State loaded from {self.state_file}")
            return state_data
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}", exc_info=True)
            return None
    
    def create_checkpoint(self, name: str, data: Any) -> bool:
        """
        Create a checkpoint of specific data
        
        Args:
            name: Checkpoint name
            data: Data to save
        
        Returns:
            True if successful
        """
        try:            
            checkpoint_file = self.checkpoint_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
            
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"Checkpoint created: {checkpoint_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}", exc_info=True)
            return False
    
    def load_checkpoint(self, name: str) -> Optional[Any]:
        """
        Load the most recent checkpoint with given name
        
        Args:
            name: Checkpoint name pattern
        
        Returns:
            Checkpoint data or None
        """
        try:
            # Find most recent checkpoint matching name
            checkpoints = sorted(self.checkpoint_dir.glob(f"{name}_*.pkl"), 
                               key=lambda p: p.stat().st_mtime, 
                               reverse=True)
            
            if not checkpoints:
                logger.info(f"No checkpoint found for: {name}")
                return None
            
            latest = checkpoints[0]
            
            with open(latest, 'rb') as f:
                data = pickle.load(f)
            
            logger.info(f"Checkpoint loaded: {latest}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}", exc_info=True)
            return None
    
    def clear_old_checkpoints(self, keep_count: int = 5) -> None:
        """Remove old checkpoints, keeping only the most recent"""
        try:
            all_checkpoints = sorted(self.checkpoint_dir.glob("*.pkl"),
                                    key=lambda p: p.stat().st_mtime,
                                    reverse=True)
            
            for checkpoint in all_checkpoints[keep_count:]:
                checkpoint.unlink()
                logger.debug(f"Removed old checkpoint: {checkpoint}")
                
        except Exception as e:
            logger.error(f"Failed to clear old checkpoints: {e}")


class GoalPersistence:
    """Persist and restore active goals"""
    
    def __init__(self, persistence: StatePersistence):
        self.persistence = persistence
    
    def save_goals(self, goals: list) -> bool:
        """Save active goals"""
        try:
            goals_data = []
            for goal in goals:
                goal_dict = {
                    "id": goal.id,
                    "description": goal.description,
                    "objective": goal.objective,
                    "priority": goal.priority.value if hasattr(goal.priority, 'value') else goal.priority,
                    "status": goal.status.value if hasattr(goal.status, 'value') else goal.status,
                    "tasks": [
                        {
                            "description": task.description,
                            "action_type": task.action_type,
                            "parameters": task.parameters,
                            "status": task.status.value if hasattr(task.status, 'value') else task.status
                        }
                        for task in goal.tasks
                    ]
                }
                goals_data.append(goal_dict)
            
            return self.persistence.save_state({"active_goals": goals_data})
            
        except Exception as e:
            logger.error(f"Failed to save goals: {e}", exc_info=True)
            return False
    
    def load_goals(self):
        """Load saved goals (returns raw data for reconstruction)"""
        try:
            state = self.persistence.load_state()
            if state and "active_goals" in state:
                return state["active_goals"]
            return []
            
        except Exception as e:
            logger.error(f"Failed to load goals: {e}", exc_info=True)
            return []


# Global instance
_state_persistence = None
_goal_persistence = None

def get_state_persistence() -> StatePersistence:
    """Get global state persistence instance"""
    global _state_persistence
    if _state_persistence is None:
        _state_persistence = StatePersistence()
    return _state_persistence

def get_goal_persistence() -> GoalPersistence:
    """Get global goal persistence instance"""
    global _goal_persistence
    if _goal_persistence is None:
        _goal_persistence = GoalPersistence(get_state_persistence())
    return _goal_persistence
