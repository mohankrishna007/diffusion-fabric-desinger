"""
Debug script to test configuration loading and pipeline initialization
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import stages first to trigger registration
print("=== Importing stages ===")
try:
    import weaver.diffusion.stages
    stage_count = weaver.diffusion.stages.get_registered_stage_count()
    print(f"✓ Registered {stage_count} stages")
except Exception as e:
    print(f"✗ Failed to import stages: {e}")
    import traceback
    traceback.print_exc()

# Load configuration
print("\n=== Loading configuration ===")
try:
    from weaver.shared.config_loader import load_pipeline_config
    config = load_pipeline_config()
    print(f"✓ Config loaded with keys: {list(config.keys())}")
    if 'stages' in config:
        print(f"✓ Found {len(config['stages'])} stages in config")
        for stage in config['stages'][:3]:  # Show first 3
            print(f"  - {stage.get('id')}: {stage.get('name')}")
    else:
        print("✗ No 'stages' key in config")
except Exception as e:
    print(f"✗ Failed to load config: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Initialize pipeline service
print("\n=== Initializing pipeline service ===")
try:
    from weaver.diffusion import DiffusionPipelineService
    service = DiffusionPipelineService(config=config)
    print(f"✓ Service initialized")
    
    # Check execution order
    execution_order = service.pipeline_engine.get_execution_order()
    print(f"✓ Execution order: {execution_order}")
except Exception as e:
    print(f"✗ Failed to initialize service: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== Success! ===")
print("Configuration and pipeline initialization working correctly")
