"""
FL-DDoS Project Validation Script

Comprehensive validation that checks:
1. Python version
2. Dependencies installed
3. Data files present
4. Project structure
5. Import tests
6. Quick functionality tests
"""

import sys
import os
from pathlib import Path
import importlib
import subprocess

# ANSI colors for pretty output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class ProjectValidator:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        
    def print_header(self, text):
        """Print section header"""
        print(f"\n{BLUE}{'='*70}")
        print(f"{text}")
        print(f"{'='*70}{RESET}\n")
    
    def print_success(self, text):
        """Print success message"""
        print(f"{GREEN}✓{RESET} {text}")
        self.passed += 1
    
    def print_error(self, text):
        """Print error message"""
        print(f"{RED}✗{RESET} {text}")
        self.failed += 1
    
    def print_warning(self, text):
        """Print warning message"""
        print(f"{YELLOW}⚠{RESET} {text}")
        self.warnings += 1
    
    def check_python_version(self):
        """Check Python version >= 3.10"""
        self.print_header("1. Python Version Check")
        
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        
        if version.major >= 3 and version.minor >= 10:
            self.print_success(f"Python {version_str} (required: 3.10+)")
            return True
        else:
            self.print_error(f"Python {version_str} - need 3.10+")
            return False
    
    def check_dependencies(self):
        """Check if all required packages are installed"""
        self.print_header("2. Dependencies Check")
        
        required_packages = [
            'numpy',
            'pandas',
            'tensorflow',
            'scikit-learn',
            'keras',
            'requests',
            'python-dotenv',
            'pyyaml',
            'matplotlib',
            'seaborn'
        ]
        
        all_installed = True
        for package in required_packages:
            try:
                importlib.import_module(package.replace('-', '_'))
                self.print_success(f"{package}")
            except ImportError:
                self.print_error(f"{package} - NOT INSTALLED")
                all_installed = False
        
        return all_installed
    
    def check_project_structure(self):
        """Check if key directories and files exist"""
        self.print_header("3. Project Structure Check")
        
        required_paths = [
            ('docs/', True),
            ('scripts/', True),
            ('experiments/', True),
            ('tests/', True),
            ('projects/', True),
            ('config/', True),
            ('data/', True),
            ('requirements.txt', False),
            ('.env.example', False),
            ('README.md', False)
        ]
        
        all_exist = True
        for path, is_dir in required_paths:
            full_path = Path(path)
            if is_dir:
                if full_path.is_dir():
                    self.print_success(f"{path}")
                else:
                    self.print_error(f"{path} - MISSING")
                    all_exist = False
            else:
                if full_path.is_file():
                    self.print_success(f"{path}")
                else:
                    self.print_error(f"{path} - MISSING")
                    all_exist = False
        
        return all_exist
    
    def check_data_files(self):
        """Check if processed data files exist"""
        self.print_header("4. Data Files Check")
        
        data_files = [
            'data/processed/cicddos2019_full_processed.npz',
            'data/processed/cicddos2019_full_processed_feature_selection.pkl'
        ]
        
        all_exist = True
        for data_file in data_files:
            if Path(data_file).is_file():
                size_mb = Path(data_file).stat().st_size / (1024 * 1024)
                self.print_success(f"{data_file} ({size_mb:.1f} MB)")
            else:
                self.print_warning(f"{data_file} - MISSING (run data preprocessing)")
                all_exist = False
        
        # Optional datasets
        optional_files = [
            'data/processed/unsw_nb15_processed.npz'
        ]
        
        for opt_file in optional_files:
            if Path(opt_file).is_file():
                self.print_success(f"{opt_file} (optional)")
            else:
                self.print_warning(f"{opt_file} - optional, not critical")
        
        return all_exist
    
    def check_imports(self):
        """Test if key project modules can be imported"""
        self.print_header("5. Module Import Tests")
        
        sys.path.insert(0, str(Path.cwd()))
        
        modules_to_test = [
            ('projects.shared_libs', 'CNNBiLSTMModel'),
            ('projects.fl.aggregation_server', 'FederatedServer'),
            ('projects.fl.fl_node_client', 'FLNode'),
            ('projects.shared_libs.trust_manager', 'TrustManager'),
            ('projects.shared_libs.byzantine_defense', 'ByzantineRobustAggregator'),
            ('projects.shared_libs.simple_openrouter', 'SimpleOpenRouterClient'),
            ('projects.shared_libs.agent_coordinator', 'FLAgentCoordinator')
        ]
        
        all_imported = True
        for module_name, class_name in modules_to_test:
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, class_name):
                    self.print_success(f"{module_name}.{class_name}")
                else:
                    self.print_error(f"{module_name}.{class_name} - CLASS NOT FOUND")
                    all_imported = False
            except Exception as e:
                self.print_error(f"{module_name} - IMPORT FAILED: {str(e)[:50]}")
                all_imported = False
        
        return all_imported
    
    def check_tensorflow(self):
        """Check TensorFlow installation and GPU availability"""
        self.print_header("6. TensorFlow Check")
        
        try:
            import tensorflow as tf
            self.print_success(f"TensorFlow version: {tf.__version__}")
            
            # GPU check
            gpus = tf.config.list_physical_devices('GPU')
            if gpus:
                self.print_success(f"GPU available: {len(gpus)} device(s)")
            else:
                self.print_warning("No GPU detected - will use CPU (slower)")
            
            return True
        except Exception as e:
            self.print_error(f"TensorFlow check failed: {str(e)[:50]}")
            return False
    
    def check_environment(self):
        """Check .env configuration"""
        self.print_header("7. Environment Configuration")
        
        if Path('.env').is_file():
            self.print_success(".env file exists")
            
            try:
                from dotenv import load_dotenv
                import os
                load_dotenv()
                
                # Check for OpenRouter API key (optional)
                api_key = os.getenv('OPENROUTER_API_KEY')
                if api_key and api_key != 'your_api_key_here':
                    self.print_success("OPENROUTER_API_KEY configured")
                else:
                    self.print_warning("OPENROUTER_API_KEY not set (LLM features will use mock mode)")
                
            except Exception as e:
                self.print_warning(f"Could not load .env: {str(e)[:50]}")
        else:
            self.print_warning(".env not found (using .env.example as template)")
        
        return True
    
    def run_quick_test(self):
        """Run a quick functionality test"""
        self.print_header("8. Quick Functionality Test")
        
        try:
            import numpy as np
            sys.path.insert(0, str(Path.cwd()))
            
            # Test 1: Load a small amount of data
            data_file = Path('data/processed/cicddos2019_full_processed.npz')
            if data_file.exists():
                data = np.load(data_file)
                X = data['X'][:100]  # Just 100 samples
                y = data['y'][:100]
                self.print_success(f"Data loading: {X.shape}")
            else:
                self.print_warning("Skipping data test - data not found")
                return True
            
            # Test 2: Import CNNBiLSTMModel
            from projects.shared_libs import CNNBiLSTMModel
            self.print_success("CNNBiLSTMModel import")
            
            # Test 3: Create a small model
            from scripts.data.load_cicddos import reshape_for_cnn_bilstm
            X_reshaped = reshape_for_cnn_bilstm(X, timesteps=10)
            
            model = CNNBiLSTMModel(
                input_shape=X_reshaped.shape[1:],
                num_classes=len(np.unique(y)),
                cnn_filters=(32,),  # Smaller for testing
                lstm_units=(32,),
                dropout_rate=0.3
            )
            self.print_success(f"Model creation: {model.model.count_params()} parameters")
            
            return True
            
        except Exception as e:
            self.print_error(f"Functionality test failed: {str(e)[:100]}")
            return False
    
    def print_summary(self):
        """Print validation summary"""
        self.print_header("VALIDATION SUMMARY")
        
        total = self.passed + self.failed
        
        print(f"Passed:   {GREEN}{self.passed}{RESET}")
        print(f"Failed:   {RED}{self.failed}{RESET}")
        print(f"Warnings: {YELLOW}{self.warnings}{RESET}")
        print(f"Total:    {total}\n")
        
        if self.failed == 0:
            print(f"{GREEN}✓ ALL CHECKS PASSED! Project is ready to use.{RESET}\n")
            return True
        else:
            print(f"{RED}✗ {self.failed} checks failed. Please fix the issues above.{RESET}\n")
            return False
    
    def run_all_checks(self):
        """Run all validation checks"""
        print(f"\n{BLUE}{'='*70}")
        print("FL-DDOS PROJECT VALIDATION")
        print(f"{'='*70}{RESET}\n")
        
        self.check_python_version()
        self.check_dependencies()
        self.check_project_structure()
        self.check_data_files()
        self.check_imports()
        self.check_tensorflow()
        self.check_environment()
        self.run_quick_test()
        
        return self.print_summary()


def main():
    """Main validation entry point"""
    validator = ProjectValidator()
    success = validator.run_all_checks()
    
    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
