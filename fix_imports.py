"""
Fix Python Path for all reorganized scripts.

Adds sys.path setup to all moved Python files so they can find the projects module.
"""

import os
from pathlib import Path

# Path setup code to add
PATH_SETUP = """import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent{}
sys.path.insert(0, str(project_root))

"""

def add_path_setup(file_path: Path, levels_up: int):
    """Add path setup to a Python file"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already has path setup
    if 'project_root = Path(__file__)' in content:
        print(f"  ✓ Already fixed: {file_path.name}")
        return
    
    # Find where to insert (after docstring, before imports)
    lines = content.split('\n')
    insert_idx = 0
    
    # Skip docstring
    in_docstring = False
    for i, line in enumerate(lines):
        if '"""' in line or "'''" in line:
            in_docstring = not in_docstring
            if not in_docstring:
                insert_idx = i + 1
                break
    
    # Skip empty lines
    while insert_idx < len(lines) and not lines[insert_idx].strip():
        insert_idx += 1
    
    # Create path setup with correct number of parent levels
    parent_string = '.parent' * levels_up
    path_code = PATH_SETUP.format(parent_string)
    
    # Insert path setup
    new_lines = lines[:insert_idx] + path_code.split('\n') + lines[insert_idx:]
    new_content = '\n'.join(new_lines)
    
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"  ✅ Fixed: {file_path.name}")


def main():
    print("Fixing Python paths for reorganized files...\n")
    
    root = Path(__file__).parent
    
    # Scripts - 2 levels up (scripts/data/file.py -> ../../)
    print("📁 scripts/data/")
    for file in (root / 'scripts' / 'data').glob('*.py'):
        if file.name != '__init__.py':
            add_path_setup(file, 2)
    
    print("\n📁 scripts/training/")
    for file in (root / 'scripts' / 'training').glob('*.py'):
        if file.name != '__init__.py':
            add_path_setup(file, 2)
    
    print("\n📁 scripts/")
    for file in (root / 'scripts').glob('*.py'):
        if file.name != '__init__.py' and file.is_file():
            add_path_setup(file, 1)
    
    # Experiments - 3 levels up (experiments/category/file.py -> ../../../)
    print("\n📁 experiments/feature_selection/")
    for file in (root / 'experiments' / 'feature_selection').glob('*.py'):
        if file.name != '__init__.py':
            add_path_setup(file, 3)
    
    print("\n📁 experiments/federated_learning/")
    for file in (root / 'experiments' / 'federated_learning').glob('*.py'):
        if file.name != '__init__.py':
            add_path_setup(file, 3)
    
    print("\n📁 experiments/extended/")
    for file in (root / 'experiments' / 'extended').glob('*.py'):
        if file.name != '__init__.py':
            add_path_setup(file, 3)
    
    # Tests - 2 levels up (tests/file.py -> ../../)
    print("\n📁 tests/")
    for file in (root / 'tests').glob('*.py'):
        if file.name != '__init__.py':
            add_path_setup(file, 2)
    
    print("\n✅ All files fixed!")


if __name__ == "__main__":
    main()
