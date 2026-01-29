"""
Weaver AI - Fabric Design Studio
Transform your designs into production-ready patterns
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
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import stages (internal)
try:
    import weaver.diffusion.stages
    stage_count = len(weaver.diffusion.stages.STAGE_CLASSES)
except Exception as e:
    stage_count = 0

from ui.pipeline_service import PipelineService
from ui.config_detector import ConfigDetector
from weaver.shared.constants import (
    MIN_DPI, MAX_DPI, LOSSLESS_INPUT_FORMATS,
    MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT, MAX_FILE_SIZE_BYTES
)


# Page configuration
st.set_page_config(
    page_title="Weaver AI - Fabric Design Studio",
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
    st.markdown('<div class="main-header">🧵 Weaver AI Design Studio</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Transform your designs into beautiful, production-ready fabric patterns</div>', unsafe_allow_html=True)
    st.markdown("---")


def display_sidebar_info():
    """Display information in sidebar."""
    with st.sidebar:
        st.image("https://via.placeholder.com/300x100/2E86AB/FFFFFF?text=Weaver+AI", width='stretch')
        
        st.markdown("### 🎨 How It Works")
        st.markdown("""
        1. **Upload** your fabric design
        2. **Review** pattern settings
        3. **Process** with AI enhancement
        4. **Download** production files
        """)
        
        st.markdown("---")
        st.markdown("### 📖 Accepted File Types")
        st.markdown("Upload high-quality images in:")
        for fmt in LOSSLESS_INPUT_FORMATS:
            st.markdown(f"- {fmt.upper().replace('.', '')} format")
        st.info("💡 JPEG not supported - use PNG for best results")
        
        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.markdown("""
        Weaver AI uses advanced AI to refine your fabric designs
        while ensuring they meet production requirements.
        
        Perfect for textile designers, manufacturers, and studios.
        """)


def handle_image_upload():
    """Handle image upload and display preview."""
    st.markdown("## 📤 Upload Your Design")
    
    uploaded_file = st.file_uploader(
        "Choose your fabric design image",
        type=['png', 'tiff', 'tif', 'bmp'],
        help="Upload PNG, TIFF, or BMP format. High resolution images work best."
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
        with st.spinner("🔍 Analyzing your design..."):
            try:
                detected = st.session_state.config_detector.detect_config(str(temp_file_path))
                st.session_state.detected_config = detected
                st.success(f"✅ Design loaded: {detected['image_width']}×{detected['image_height']} pixels at {detected['dpi']} DPI")
            except Exception as e:
                st.error(f"❌ Could not analyze image. Please try a different file.")
                st.session_state.detected_config = None
        
        # Display image preview
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 🖼️ Preview")
            try:
                img = Image.open(temp_file_path)
                st.image(img, caption=uploaded_file.name, use_container_width=True)
            except Exception as e:
                st.error(f"Could not display preview")
                return False
        
        with col2:
            st.markdown("### 📊 Design Details")
            try:
                img = Image.open(temp_file_path)
                st.markdown(f"**File:** {uploaded_file.name}")
                st.markdown(f"**Format:** {img.format}")
                st.markdown(f"**Dimensions:** {img.size[0]:,} × {img.size[1]:,} pixels")
                st.markdown(f"**File Size:** {uploaded_file.size / 1024 / 1024:.1f} MB" if uploaded_file.size > 1024*1024 else f"**File Size:** {uploaded_file.size / 1024:.1f} KB")
            except Exception as e:
                st.error(f"Could not read image details")
        
        return True
    
    return False


def detect_and_display_config():
    """Detect configuration from uploaded image and allow user to edit."""
    if st.session_state.uploaded_image_path is None:
        return None
    
    st.markdown("---")
    st.markdown("## ⚙️ Pattern Settings")
    
    # Configuration should already be detected from upload
    if st.session_state.detected_config is not None:
        config = st.session_state.detected_config
        
        st.markdown("### 📐 Review Your Design Settings")
        st.markdown('<div class="info-box">We automatically detected your image properties. You can adjust the repeat pattern size below.</div>', unsafe_allow_html=True)
        
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
            st.markdown("#### 📊 Image Properties")
            
            # Display detected properties
            st.markdown(f"**Resolution:** {config['dpi']} DPI")
            st.markdown(f"**Colors:** {config['color_mode']}")
            st.markdown(f"**Size:** {config['image_width']:,} × {config['image_height']:,} px")
            
            st.caption("These values are automatically detected from your image.")
            
            # Store detected values for pipeline execution
            st.session_state.form_dpi = config['dpi']
            st.session_state.form_color_mode = config['color_mode']
        
        with col2:
            st.markdown("#### 🔄 Pattern Repeat Size")
            
            # Repeat Width
            repeat_width = st.number_input(
                "Repeat Width (pixels)",
                min_value=1,
                max_value=MAX_IMAGE_WIDTH,
                value=st.session_state.form_repeat_width,
                step=1,
                key='repeat_width_input',
                help="How wide is one repeating pattern tile?"
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
                help="How tall is one repeating pattern tile?"
            )
            st.session_state.form_repeat_height = repeat_height
        
        # Display validation warnings
        img_width = config.get('image_width', 0)
        img_height = config.get('image_height', 0)
        
        # Check tiling
        if img_width % repeat_width != 0 or img_height % repeat_height != 0:
            st.markdown('<div class="warning-box">⚠️ <strong>Tiling Issue:</strong> Your repeat size doesn\'t divide evenly into the image. Please adjust the repeat dimensions for perfect tiling.</div>', unsafe_allow_html=True)
            st.markdown(f"Current pattern would create {img_width / repeat_width:.1f} × {img_height / repeat_height:.1f} tiles (needs whole numbers)")
        else:
            tiles_h = img_width // repeat_width
            tiles_v = img_height // repeat_height
            st.markdown(f'<div class="success-box">✅ Perfect! Your pattern will tile seamlessly with {tiles_h} × {tiles_v} repeats.</div>', unsafe_allow_html=True)
        
        # Display helpful suggestions
        suggestions = config.get('suggestions', [])
        if suggestions:
            with st.expander("💡 Helpful Tips", expanded=False):
                for suggestion in suggestions:
                    st.markdown(f"- {suggestion}")
        
        # Build final config and store in session state
        final_config = {
            'dpi': st.session_state.form_dpi,
            'color_mode': st.session_state.form_color_mode,
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
        if st.button("✨ Create Production Pattern", type="primary", use_container_width=True):
            
            # Use config from session state (most recent form values)
            pipeline_config = st.session_state.get('final_config', config)
            
            # Create progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Run pipeline
                status_text.text("Processing your design...")
                progress_bar.progress(10)
                
                result = st.session_state.pipeline_service.execute_pipeline(
                    image_path=st.session_state.uploaded_image_path,
                    config=pipeline_config,
                    progress_callback=lambda stage, message: update_progress(
                        stage, message, progress_bar, status_text
                    )
                )
                
                progress_bar.progress(100)
                status_text.text("✅ Complete!")
                
                st.session_state.pipeline_result = result
                
                st.balloons()
                st.success("🎉 Your production-ready pattern is ready!")
                
            except Exception as e:
                st.error(f"❌ Processing failed. Please check your image and try again.")
                # Show simple error for users, hide technical details
                with st.expander("Technical Details (for support)"):
                    st.code(str(e))
                st.session_state.pipeline_result = None


def update_progress(stage: int, message: str, progress_bar, status_text):
    """Update progress indicators."""
    stage_names = [
        "Validating image",
        "Optimizing quality", 
        "Analyzing structure",
        "AI enhancement",
        "Perfecting repeat",
        "Refining details",
        "Adjusting colors",
        "Final verification"
    ]
    progress = min(10 + (stage + 1) * 11, 100)
    progress_bar.progress(progress)
    stage_name = stage_names[stage] if stage < len(stage_names) else "Processing"
    status_text.text(f"⏳ {stage_name}...")


def display_pipeline_results():
    """Display pipeline execution results."""
    if st.session_state.pipeline_result is not None:
        st.markdown("---")
        st.markdown("## ✨ Your Pattern is Ready!")
        
        result = st.session_state.pipeline_result
        
        # Success message
        st.markdown('<div class="success-box">', unsafe_allow_html=True)
        st.markdown("### 🎉 Processing Complete!")
        st.markdown("Your fabric design has been transformed into a production-ready pattern.")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Display key information in a simple format
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📥 Download Your Pattern")
            st.markdown("Your pattern files are ready for production.")
            
            # Show download buttons (when artifacts are available)
            st.button("📄 Download Pattern Files", disabled=True, help="Pattern export coming soon")
            st.button("📊 Download Technical Report", disabled=True, help="Report export coming soon")
        
        with col2:
            st.markdown("### 📋 Pattern Details")
            
            # Show simple, client-friendly metrics
            stage_outputs = result.get('stage_outputs', {})
            processing_steps = len(stage_outputs)
            
            st.markdown(f"**Processing Steps:** {processing_steps} completed")
            
            if 'created_at' in result:
                created_at = result['created_at']
                if isinstance(created_at, str):
                    created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created = created_at
                st.markdown(f"**Processed:** {created.strftime('%I:%M %p')}")
            
            # Show reference ID (simplified)
            pipeline_id = result.get('pipeline_id', 'N/A')[:8]
            st.markdown(f"**Reference:** {pipeline_id}")
        
        # Technical details for advanced users (collapsed by default)
        with st.expander("🔧 Technical Details", expanded=False):
            st.caption("For designers and technical teams")
            
            for stage_id in stage_outputs.keys():
                stage_data = stage_outputs[stage_id]
                st.markdown(f"**{stage_id}:** Completed")
            
            st.json(result, expanded=False)


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
        # Welcome message for new users
        st.markdown("### 👋 Welcome to Weaver AI!")
        st.markdown("Upload your fabric design to get started. We'll transform it into a production-ready pattern.")
        st.info("💡 **Tip:** Use high-resolution PNG files for best results")


if __name__ == "__main__":
    main()
