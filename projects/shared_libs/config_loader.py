import yaml
import os

class ConfigLoader:
    """Load configuration from YAML files"""
    
    @staticmethod
    def load(config_path):
        """Load YAML configuration file"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    
    @staticmethod
    def save(config, config_path):
        """Save configuration to YAML file"""
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

# Test the loader
if __name__ == "__main__":
    test_config = {
        'node': {
            'id': 'test-001',
            'name': 'Test Node'
        }
    }
    
    ConfigLoader.save(test_config, 'config/test_config.yaml')
    loaded = ConfigLoader.load('config/test_config.yaml')
    print(f"✅ Config loaded: {loaded}")
