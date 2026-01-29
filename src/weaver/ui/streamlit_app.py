"""
Streamlit UI for Weaver AI Fabric Design Pipeline
Interactive interface for uploading images and configuring Stage 0 parameters
"""

import streamlit as st
import sys
from pathlib import Path
from PIL import Image
import tempfile
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from weaver.ui.pipeline_service import PipelineService
from weaver.ui.config_detector import ConfigDetector
from weaver.shared.constants import (
    MIN_DPI, MAX_DPI, LOSSLESS_INPUT_FORMATS,
    MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT, MAX_FILE_SIZE_BYTES
)


# Page configuration
st.set_page_config(
    page_title="Weaver AI - Fabric Design Pipeline",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E86AB;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #555;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border-left: 5px solid #17a2b8;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        margin: 1rem 0;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    if 'uploaded_image_path' not in st.session_state:
        st.session_state.uploaded_image_path = None
    if 'detected_config' not in st.session_state:
        st.session_state.detected_config = None
    if 'final_config' not in st.session_state:
        st.session_state.final_config = None
    if 'pipeline_result' not in st.session_state:
        st.session_state.pipeline_result = None
    if 'pipeline_service' not in st.session_state:
        st.session_state.pipeline_service = PipelineService()
    if 'config_detector' not in st.session_state:
        st.session_state.config_detector = ConfigDetector()


def display_header():
    """Display application header."""
    st.markdown('<div class="main-header">🧵 Weaver AI Fabric Design Pipeline</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upload fabric design images and generate manufacturing-ready patterns</div>', unsafe_allow_html=True)
    st.markdown("---")


def display_sidebar_info():
    """Display information in sidebar."""
    with st.sidebar:
        st.image("https://via.placeholder.com/300x100/2E86AB/FFFFFF?text=Weaver+AI", width='stretch')
        
        st.markdown("### 📋 Pipeline Stages")
        stages = [
            "Stage 0: Input Acquisition",
            "Stage 1: Canonical Normalization", 
            "Stage 2: Structural Intent Definition",
            "Stage 3: Controlled Diffusion Refinement",
            "Stage 4: Repeat & Boundary Enforcement",
            "Stage 5: Manufacturing Geometry Cleanup",
            "Stage 6: Color & Thread Constraint Enforcement",
            "Stage 7: Pre-CAM Validation Firewall"
        ]
        for stage in stages:
            st.markdown(f"- {stage}")
        
        st.markdown("---")
        st.markdown("### 📖 Supported Formats")
        st.markdown("**Lossless formats only:**")
        for fmt in LOSSLESS_INPUT_FORMATS:
            st.markdown(f"- `{fmt}`")
        
        st.markdown("---")
        st.markdown("### ⚙️ Manufacturing Constraints")
        st.markdown(f"- **DPI Range:** {MIN_DPI} - {MAX_DPI}")
        st.markdown(f"- **Max Dimensions:** {MAX_IMAGE_WIDTH} x {MAX_IMAGE_HEIGHT} px")
        st.markdown(f"- **Max File Size:** {MAX_FILE_SIZE_BYTES // (1024*1024)} MB")
        
        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.markdown("""
        Weaver AI transforms fabric designs into manufacturing-ready patterns
        using AI-powered processing with strict manufacturing constraints.
        """)


def handle_image_upload():
    """Handle image upload and display preview."""
    st.markdown("## 📤 Step 1: Upload Fabric Design")
    
    uploaded_file = st.file_uploader(
        "Choose a fabric design image (PNG, TIFF, or BMP only)",
        type=['png', 'tiff', 'tif', 'bmp'],
        help="Upload a lossless format image. JPEG is not supported due to compression artifacts."
    )
    
    if uploaded_file is not None:
        # Save uploaded file to temporary location
        temp_dir = Path(tempfile.gettempdir()) / "weaver_uploads"
        temp_dir.mkdir(exist_ok=True)
        
        temp_file_path = temp_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
        
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.session_state.uploaded_image_path = str(temp_file_path)
        
        # Clear previous form values when new image is uploaded
        if 'form_dpi' in st.session_state:
            del st.session_state.form_dpi
        if 'form_color_mode' in st.session_state:
            del st.session_state.form_color_mode
        if 'form_repeat_width' in st.session_state:
            del st.session_state.form_repeat_width
        if 'form_repeat_height' in st.session_state:
            del st.session_state.form_repeat_height
        
        # Auto-detect configuration immediately after upload
        with st.spinner("🔍 Analyzing image and detecting configuration..."):
            try:
                detected = st.session_state.config_detector.detect_config(str(temp_file_path))
                st.session_state.detected_config = detected
                st.success(f"✅ Auto-detected: DPI={detected['dpi']}, Mode={detected['color_mode']}, Size={detected['image_width']}x{detected['image_height']}px")
            except Exception as e:
                st.error(f"❌ Error detecting configuration: {str(e)}")
                st.session_state.detected_config = None
        
        # Display image preview
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 🖼️ Image Preview")
            try:
                img = Image.open(temp_file_path)
                st.image(img, caption=uploaded_file.name, width='stretch')
            except Exception as e:
                st.error(f"Error loading image: {str(e)}")
                return False
        
        with col2:
            st.markdown("### 📊 Image Information")
            try:
                img = Image.open(temp_file_path)
                st.markdown(f"**File Name:** {uploaded_file.name}")
                st.markdown(f"**Format:** {img.format}")
                st.markdown(f"**Mode:** {img.mode}")
                st.markdown(f"**Size:** {img.size[0]} x {img.size[1]} px")
                st.markdown(f"**File Size:** {uploaded_file.size / 1024:.2f} KB")
                
                # Check for DPI info
                dpi_info = img.info.get('dpi', None)
                if dpi_info:
                    st.markdown(f"**DPI (from file):** {dpi_info[0]:.0f}")
            except Exception as e:
                st.error(f"Error reading image metadata: {str(e)}")
        
        return True
    
    return False


def detect_and_display_config():
    """Detect configuration from uploaded image and allow user to edit."""
    if st.session_state.uploaded_image_path is None:
        return None
    
    st.markdown("---")
    st.markdown("## ⚙️ Step 2: Review & Edit Configuration")
    
    # Configuration should already be detected from upload
    if st.session_state.detected_config is not None:
        config = st.session_state.detected_config
        
        st.markdown("### 📝 Edit Configuration")
        st.markdown('<div class="info-box">Review and adjust the detected parameters below. All fields are required for Stage 0.</div>', unsafe_allow_html=True)
        
        # Show what was auto-detected
        st.info(f"**Auto-detected:** DPI={config['dpi']}, Color Mode={config['color_mode']}, Image Size={config['image_width']}x{config['image_height']}px")
        
        # Initialize widget values in session state if not already set
        if 'form_dpi' not in st.session_state:
            st.session_state.form_dpi = config['dpi']
        if 'form_color_mode' not in st.session_state:
            st.session_state.form_color_mode = config['color_mode']
        if 'form_repeat_width' not in st.session_state:
            st.session_state.form_repeat_width = config.get('repeat_unit', {}).get('width', 100)
        if 'form_repeat_height' not in st.session_state:
            st.session_state.form_repeat_height = config.get('repeat_unit', {}).get('height', 100)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Image Properties")
            
            # Use session state values
            dpi = st.number_input(
                "DPI (Dots Per Inch)",
                min_value=MIN_DPI,
                max_value=MAX_DPI,
                value=st.session_state.form_dpi,
                step=1,
                key='dpi_input',
                help=f"Declared DPI must match image metadata. Detected: {config['dpi']}"
            )
            st.session_state.form_dpi = dpi
            
            # Color Mode
            color_modes = ['RGB', 'RGBA', 'L', 'LA']
            default_index = color_modes.index(st.session_state.form_color_mode) if st.session_state.form_color_mode in color_modes else 0
            color_mode = st.selectbox(
                "Color Mode",
                options=color_modes,
                index=default_index,
                key='color_mode_input',
                help=f"Color mode must match image. Detected: {config['color_mode']}. P (palette) and 1 (1-bit) are not allowed."
            )
            st.session_state.form_color_mode = color_mode
        
        with col2:
            st.markdown("#### Repeat Unit Dimensions")
            
            # Repeat Width
            repeat_width = st.number_input(
                "Repeat Width (pixels)",
                min_value=1,
                max_value=MAX_IMAGE_WIDTH,
                value=st.session_state.form_repeat_width,
                step=1,
                key='repeat_width_input',
                help="Width of the repeating pattern unit in pixels"
            )
            st.session_state.form_repeat_width = repeat_width
            
            # Repeat Height
            repeat_height = st.number_input(
                "Repeat Height (pixels)",
                min_value=1,
                max_value=MAX_IMAGE_HEIGHT,
                value=st.session_state.form_repeat_height,
                step=1,
                key='repeat_height_input',
                help="Height of the repeating pattern unit in pixels"
            )
            st.session_state.form_repeat_height = repeat_height
        
        # Display validation warnings
        img_width = config.get('image_width', 0)
        img_height = config.get('image_height', 0)
        
        # Check if user changed from detected values
        detected_dpi = config.get('dpi', 300)
        detected_color_mode = config.get('color_mode', 'RGB')
        
        if dpi != detected_dpi or color_mode != detected_color_mode:
            st.markdown('<div class="warning-box">⚠️ <strong>Warning:</strong> You changed values from what was detected. This may cause Stage 0 validation to fail!</div>', unsafe_allow_html=True)
            if dpi != detected_dpi:
                st.markdown(f"- DPI changed: Detected **{detected_dpi}** but you entered **{dpi}**")
            if color_mode != detected_color_mode:
                st.markdown(f"- Color Mode changed: Detected **{detected_color_mode}** but you selected **{color_mode}**")
        
        # Check tiling
        if img_width % repeat_width != 0 or img_height % repeat_height != 0:
            st.markdown('<div class="warning-box">⚠️ <strong>Warning:</strong> Image dimensions are not perfectly divisible by repeat unit dimensions. Stage 0 requires perfect tiling.</div>', unsafe_allow_html=True)
            st.markdown(f"- Image size: {img_width} x {img_height} px")
            st.markdown(f"- Repeat unit: {repeat_width} x {repeat_height} px")
            st.markdown(f"- Tiles: {img_width / repeat_width:.2f} x {img_height / repeat_height:.2f}")
        else:
            st.markdown('<div class="success-box">✅ Perfect tiling detected! Image dimensions are perfectly divisible by repeat unit.</div>', unsafe_allow_html=True)
            st.markdown(f"- Tiles: {img_width // repeat_width} x {img_height // repeat_height}")
        
        # Display configuration suggestions
        suggestions = config.get('suggestions', [])
        if suggestions:
            st.markdown("### 💡 Detection Notes")
            for suggestion in suggestions:
                # Format based on suggestion type
                if '⚠️' in suggestion or 'Warning' in suggestion:
                    st.warning(suggestion)
                elif 'ℹ️' in suggestion or suggestion.startswith('✅'):
                    st.info(suggestion)
                else:
                    st.markdown(f"- {suggestion}")
        
        # Build final config and store in session state
        final_config = {
            'dpi': dpi,
            'color_mode': color_mode,
            'repeat_unit': {
                'width': repeat_width,
                'height': repeat_height
            }
        }
        
        # Store in session state for pipeline execution
        st.session_state.final_config = final_config
        
        return final_config
    
    return None


def run_pipeline(config: Dict[str, Any]):
    """Run the pipeline with the given configuration."""
    st.markdown("---")
    st.markdown("## 🚀 Step 3: Execute Pipeline")
    
    if config is None:
        st.warning("⚠️ Please upload an image first. Configuration will be detected automatically.")
        return
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("▶️ Run Pipeline", type="primary", width='stretch'):
            
            # Use config from session state (most recent form values)
            pipeline_config = st.session_state.get('final_config', config)
            
            # Debug: Show what config is being used
            st.info(f"📋 Using config: DPI={pipeline_config['dpi']}, Mode={pipeline_config['color_mode']}")
            
            # Create progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Run pipeline
                status_text.text("Initializing pipeline...")
                progress_bar.progress(10)
                
                result = st.session_state.pipeline_service.execute_pipeline(
                    image_path=st.session_state.uploaded_image_path,
                    config=pipeline_config,
                    progress_callback=lambda stage, message: update_progress(
                        stage, message, progress_bar, status_text
                    )
                )
                
                progress_bar.progress(100)
                status_text.text("Pipeline completed successfully!")
                
                st.session_state.pipeline_result = result
                
                st.balloons()
                st.success("✅ Pipeline executed successfully!")
                
            except Exception as e:
                st.error(f"❌ Pipeline execution failed: {str(e)}")
                st.session_state.pipeline_result = None


def update_progress(stage: int, message: str, progress_bar, status_text):
    """Update progress indicators."""
    progress = min(10 + (stage + 1) * 11, 100)
    progress_bar.progress(progress)
    status_text.text(f"Stage {stage}: {message}")


def display_pipeline_results():
    """Display pipeline execution results."""
    if st.session_state.pipeline_result is not None:
        st.markdown("---")
        st.markdown("## 📊 Pipeline Results")
        
        result = st.session_state.pipeline_result
        
        # Display summary
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Status", result.get('status', 'unknown').upper())
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Pipeline ID", result.get('pipeline_id', 'N/A')[:8] + "...")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            completed_stages = result.get('completed_stages', [])
            st.metric("Completed Stages", f"{len(completed_stages)}/8")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            if 'created_at' in result:
                created = datetime.fromisoformat(result['created_at'].replace('Z', '+00:00'))
                st.metric("Created", created.strftime('%H:%M:%S'))
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Display stage outputs
        st.markdown("### 📋 Stage Outputs")
        stage_outputs = result.get('stage_outputs', {})
        
        for stage_num in sorted(stage_outputs.keys()):
            stage_data = stage_outputs[stage_num]
            status = stage_data.get('status', 'unknown')
            message = stage_data.get('message', 'No message')
            
            if status == 'completed':
                st.success(f"✅ Stage {stage_num}: {message}")
            elif status == 'failed':
                st.error(f"❌ Stage {stage_num}: {message}")
            else:
                st.info(f"ℹ️ Stage {stage_num}: {message}")
        
        # Display detailed results
        with st.expander("🔍 View Detailed Results"):
            st.json(result)


def main():
    """Main application entry point."""
    initialize_session_state()
    display_header()
    display_sidebar_info()
    
    # Main workflow
    has_upload = handle_image_upload()
    
    if has_upload:
        config = detect_and_display_config()
        run_pipeline(config)
        display_pipeline_results()
    else:
        st.info("👆 Upload a fabric design image to get started")


if __name__ == "__main__":
    main()
