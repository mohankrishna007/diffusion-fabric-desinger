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
    page_title="Weaver Studio - Professional Fabric Design",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Professional Design Studio CSS
st.markdown("""
<style>
    /* Global Theme */
    :root {
        --studio-dark: #1a1a1a;
        --studio-charcoal: #2d2d2d;
        --studio-accent: #e8aa42;
        --studio-accent-hover: #d69a32;
        --studio-border: #404040;
        --studio-text: #e0e0e0;
        --studio-muted: #999999;
        --studio-success: #4caf50;
        --studio-error: #f44336;
        --studio-warning: #ff9800;
    }
    
    /* Main Container */
    .main {
        background: linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 100%);
        color: var(--studio-text);
    }
    
    /* Header Styling */
    .studio-header {
        background: var(--studio-charcoal);
        padding: 2rem 3rem;
        border-bottom: 1px solid var(--studio-border);
        margin: -1rem -1rem 2rem -1rem;
    }
    
    .studio-logo {
        font-size: 1.8rem;
        font-weight: 300;
        letter-spacing: 0.15em;
        color: var(--studio-accent);
        font-family: 'Helvetica Neue', Arial, sans-serif;
        text-transform: uppercase;
    }
    
    .studio-tagline {
        font-size: 0.9rem;
        color: var(--studio-muted);
        font-weight: 300;
        letter-spacing: 0.05em;
        margin-top: 0.25rem;
    }
    
    /* Section Headers */
    .section-title {
        font-size: 1.1rem;
        font-weight: 500;
        color: var(--studio-text);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--studio-border);
    }
    
    /* Professional Cards */
    .studio-card {
        background: var(--studio-charcoal);
        border: 1px solid var(--studio-border);
        border-radius: 4px;
        padding: 1.5rem;
        margin: 1rem 0;
        transition: border-color 0.2s ease;
    }
    
    .studio-card:hover {
        border-color: var(--studio-accent);
    }
    
    /* Status Indicators */
    .status-success {
        background: rgba(76, 175, 80, 0.1);
        border-left: 3px solid var(--studio-success);
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        border-radius: 2px;
    }
    
    .status-error {
        background: rgba(244, 67, 54, 0.1);
        border-left: 3px solid var(--studio-error);
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        border-radius: 2px;
    }
    
    .status-warning {
        background: rgba(255, 152, 0, 0.1);
        border-left: 3px solid var(--studio-warning);
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        border-radius: 2px;
    }
    
    .status-info {
        background: rgba(232, 170, 66, 0.1);
        border-left: 3px solid var(--studio-accent);
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        border-radius: 2px;
    }
    
    /* Metrics Display */
    .metric-group {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1.5rem 0;
    }
    
    .metric-item {
        background: var(--studio-charcoal);
        border: 1px solid var(--studio-border);
        padding: 1.25rem;
        border-radius: 2px;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: var(--studio-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 1.5rem;
        color: var(--studio-text);
        font-weight: 300;
    }
    
    /* Buttons */
    .stButton>button {
        background: var(--studio-accent);
        color: #000;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 500;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        transition: all 0.2s ease;
        border-radius: 2px;
    }
    
    .stButton>button:hover {
        background: var(--studio-accent-hover);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(232, 170, 66, 0.3);
    }
    
    /* File Uploader */
    .uploadedFile {
        background: var(--studio-charcoal);
        border: 1px solid var(--studio-border);
    }
    
    /* Input Fields */
    .stNumberInput>div>div>input {
        background: var(--studio-charcoal);
        border: 1px solid var(--studio-border);
        color: var(--studio-text);
        border-radius: 2px;
    }
    
    /* Progress Bar */
    .stProgress>div>div>div {
        background-color: var(--studio-accent);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: var(--studio-charcoal);
        border: 1px solid var(--studio-border);
        color: var(--studio-text);
        border-radius: 2px;
    }
    
    /* Divider */
    hr {
        border-color: var(--studio-border);
        margin: 2rem 0;
    }
    
    /* Sidebar Override */
    section[data-testid="stSidebar"] {
        background: var(--studio-charcoal);
        border-right: 1px solid var(--studio-border);
    }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
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
    """Display professional studio header."""
    st.markdown('''
    <div class="studio-header">
        <div class="studio-logo">◆ WEAVER STUDIO</div>
        <div class="studio-tagline">Professional Fabric Design & Pattern Engineering</div>
    </div>
    ''', unsafe_allow_html=True)


def display_sidebar_info():
    """Display professional sidebar information."""
    with st.sidebar:
        st.markdown("### WORKFLOW")
        st.markdown("""
        <div style='color: #999; font-size: 0.9rem; line-height: 1.8;'>
        <strong style='color: #e8aa42;'>01</strong> Import Design<br>
        <strong style='color: #e8aa42;'>02</strong> Configure Parameters<br>
        <strong style='color: #e8aa42;'>03</strong> Process Pattern<br>
        <strong style='color: #e8aa42;'>04</strong> Export Production Files
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### SPECIFICATIONS")
        st.markdown("""
        <div style='color: #999; font-size: 0.85rem; line-height: 1.6;'>
        <strong>Supported Formats</strong><br>
        PNG • TIFF • BMP<br><br>
        <strong>Resolution</strong><br>
        300-600 DPI recommended<br><br>
        <strong>Max Dimensions</strong><br>
        10,000 × 10,000 pixels
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown(f"""
        <div style='color: #666; font-size: 0.75rem; margin-top: 2rem;'>
        Weaver Studio v1.0<br>
        © 2026 All Rights Reserved
        </div>
        """, unsafe_allow_html=True)


def handle_image_upload():
    """Handle image upload with professional interface."""
    st.markdown('<div class="section-title">01 — Import Design</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Select high-resolution fabric design",
        type=['png', 'tiff', 'tif', 'bmp'],
        help="Supported: PNG, TIFF, BMP | Recommended: 300+ DPI",
        label_visibility="collapsed"
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
        with st.spinner("Analyzing design properties..."):
            try:
                detected = st.session_state.config_detector.detect_config(str(temp_file_path))
                st.session_state.detected_config = detected
                st.markdown(f'''
                <div class="status-success">
                    <strong>Design Loaded Successfully</strong><br>
                    {detected['image_width']:,} × {detected['image_height']:,} px @ {detected['dpi']} DPI
                </div>
                ''', unsafe_allow_html=True)
            except Exception as e:
                st.markdown('''
                <div class="status-error">
                    <strong>Analysis Failed</strong><br>
                    Unable to process image. Please verify file integrity.
                </div>
                ''', unsafe_allow_html=True)
                st.session_state.detected_config = None
        
        # Display image preview with metrics
        st.markdown('<div class="section-title">Design Preview</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            try:
                img = Image.open(temp_file_path)
                st.image(img, use_container_width=True)
            except Exception as e:
                st.error("Unable to render preview")
                return False
        
        with col2:
            try:
                img = Image.open(temp_file_path)
                file_size_mb = uploaded_file.size / (1024 * 1024)
                
                st.markdown(f"""
                <div class="studio-card">
                    <div class="metric-label">File Name</div>
                    <div style="color: #e0e0e0; font-size: 0.9rem; margin-bottom: 1rem;">{uploaded_file.name}</div>
                    
                    <div class="metric-label">Format</div>
                    <div style="color: #e0e0e0; font-size: 0.9rem; margin-bottom: 1rem;">{img.format}</div>
                    
                    <div class="metric-label">Dimensions</div>
                    <div style="color: #e0e0e0; font-size: 0.9rem; margin-bottom: 1rem;">{img.size[0]:,} × {img.size[1]:,} px</div>
                    
                    <div class="metric-label">File Size</div>
                    <div style="color: #e0e0e0; font-size: 0.9rem;">{file_size_mb:.2f} MB</div>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error("Unable to read metadata")
        
        return True
    
    return False


def detect_and_display_config():
    """Professional configuration interface."""
    if st.session_state.uploaded_image_path is None:
        return None
    
    st.markdown('<div class="section-title">02 — Configure Parameters</div>', unsafe_allow_html=True)
    
    # Configuration should already be detected from upload
    if st.session_state.detected_config is not None:
        config = st.session_state.detected_config
        
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
            
            # Display detected properties in professional metrics format
            st.markdown(f"""
            <div class="metric-group">
                <div class="metric-item">
                    <div class="metric-label">Resolution</div>
                    <div class="metric-value">{config['dpi']} <span style="font-size: 0.8rem; color: #999;">DPI</span></div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Color Mode</div>
                    <div class="metric-value" style="font-size: 1.1rem;">{config['color_mode']}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Dimensions</div>
                    <div class="metric-value" style="font-size: 1rem;">{config['image_width']:,} × {config['image_height']:,} <span style="font-size: 0.8rem; color: #999;">px</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Store detected values for pipeline execution
            st.session_state.form_dpi = config['dpi']
            st.session_state.form_color_mode = config['color_mode']
        
        with col2:
            st.markdown("#### Pattern Repeat Configuration")
            
            # Repeat Width
            repeat_width = st.number_input(
                "Repeat Width (pixels)",
                min_value=1,
                max_value=MAX_IMAGE_WIDTH,
                value=st.session_state.form_repeat_width,
                step=1,
                key='repeat_width_input',
                help="Width of one complete pattern tile"
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
                help="Height of one complete pattern tile"
            )
            st.session_state.form_repeat_height = repeat_height
        
        # Display validation status
        img_width = config.get('image_width', 0)
        img_height = config.get('image_height', 0)
        
        # Check tiling
        if img_width % repeat_width != 0 or img_height % repeat_height != 0:
            st.markdown(f'''
            <div class="status-warning">
                <strong>Tiling Configuration Issue</strong><br>
                Current repeat dimensions do not tile evenly: {img_width / repeat_width:.2f} × {img_height / repeat_height:.2f} tiles<br>
                <em>Adjust dimensions for seamless tiling (whole numbers required)</em>
            </div>
            ''', unsafe_allow_html=True)
        else:
            tiles_h = img_width // repeat_width
            tiles_v = img_height // repeat_height
            st.markdown(f'''
            <div class="status-success">
                <strong>Seamless Tiling Verified</strong><br>
                Pattern will tile perfectly with {tiles_h} × {tiles_v} repeats
            </div>
            ''', unsafe_allow_html=True)
        
        # Display suggestions in professional format
        suggestions = config.get('suggestions', [])
        if suggestions:
            with st.expander("Optimization Recommendations", expanded=False):
                for i, suggestion in enumerate(suggestions, 1):
                    st.markdown(f"**{i}.** {suggestion}")
        
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
    """Run the pipeline with professional execution interface."""
    st.markdown('<div class="section-title">03 — Process Pattern</div>', unsafe_allow_html=True)
    
    if config is None:
        st.markdown('''
        <div class="status-info">
            <strong>Configuration Required</strong><br>
            Complete steps 01 and 02 before processing.
        </div>
        ''', unsafe_allow_html=True)
        return
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("EXECUTE PIPELINE", type="primary", use_container_width=True):
            
            # Use config from session state (most recent form values)
            pipeline_config = st.session_state.get('final_config', config)
            
            # Create progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Run pipeline
                status_text.text("Initializing pipeline stages...")
                progress_bar.progress(10)
                
                result = st.session_state.pipeline_service.execute_pipeline(
                    image_path=st.session_state.uploaded_image_path,
                    config=pipeline_config,
                    progress_callback=lambda stage, message: update_progress(
                        stage, message, progress_bar, status_text
                    )
                )
                
                progress_bar.progress(100)
                status_text.text("Pipeline execution complete")
                
                st.session_state.pipeline_result = result
                
                st.markdown('''
                <div class="status-success">
                    <strong>Processing Complete</strong><br>
                    Production-ready pattern generated successfully.
                </div>
                ''', unsafe_allow_html=True)
                
            except Exception as e:
                st.markdown('''
                <div class="status-error">
                    <strong>Pipeline Execution Failed</strong><br>
                    Verify input parameters and file integrity.
                </div>
                ''', unsafe_allow_html=True)
                with st.expander("Error Details", expanded=False):
                    st.code(str(e), language="text")
                st.session_state.pipeline_result = None


def update_progress(stage: int, message: str, progress_bar, status_text):
    """Update progress indicators with professional terminology."""
    stage_names = [
        "Input validation",
        "Quality normalization", 
        "Structural analysis",
        "Pattern recognition",
        "Repeat enforcement",
        "Detail refinement",
        "Color calibration",
        "Output verification"
    ]
    progress = min(10 + (stage + 1) * 11, 100)
    progress_bar.progress(progress)
    stage_name = stage_names[stage] if stage < len(stage_names) else "Processing"
    status_text.text(f"Stage {stage + 1}: {stage_name}...")


def display_pipeline_results():
    """Display pipeline results with professional styling."""
    if st.session_state.pipeline_result is not None:
        st.markdown('<div class="section-title">04 — Export Production Files</div>', unsafe_allow_html=True)
        
        result = st.session_state.pipeline_result
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Export Options")
            
            st.markdown("""
            <div class="studio-card">
                <div style="margin-bottom: 1rem;">
                    <div class="metric-label">Pattern Files</div>
                    <div style="color: #999; font-size: 0.85rem; margin-top: 0.5rem;">
                    Production-ready vector patterns with complete technical specifications
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.button("EXPORT PATTERN FILES", disabled=True, use_container_width=True, help="Export functionality in development")
            
            st.markdown("""
            <div class="studio-card" style="margin-top: 1rem;">
                <div style="margin-bottom: 1rem;">
                    <div class="metric-label">Technical Report</div>
                    <div style="color: #999; font-size: 0.85rem; margin-top: 0.5rem;">
                    Comprehensive analysis report with metrics and validation data
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.button("EXPORT TECHNICAL REPORT", disabled=True, use_container_width=True, help="Report export in development")
        
        with col2:
            st.markdown("#### Processing Summary")
            
            # Show professional metrics
            stage_outputs = result.get('stage_outputs', {})
            processing_steps = len(stage_outputs)
            
            if 'created_at' in result:
                created_at = result['created_at']
                if isinstance(created_at, str):
                    created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created = created_at
                timestamp = created.strftime('%Y-%m-%d %H:%M:%S')
            else:
                timestamp = "N/A"
            
            pipeline_id = result.get('pipeline_id', 'N/A')[:12]
            
            st.markdown(f"""
            <div class="metric-group">
                <div class="metric-item">
                    <div class="metric-label">Stages Completed</div>
                    <div class="metric-value">{processing_steps}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Processed</div>
                    <div class="metric-value" style="font-size: 0.9rem;">{timestamp}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Pipeline ID</div>
                    <div class="metric-value" style="font-size: 0.9rem; font-family: monospace;">{pipeline_id}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Technical details for advanced users
        with st.expander("Stage Execution Details", expanded=False):
            st.markdown("**Pipeline Stages**")
            for stage_id in stage_outputs.keys():
                st.markdown(f"- `{stage_id}`: Completed")
            
            with st.expander("Complete Result Data", expanded=False):
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
        # Professional welcome screen
        st.markdown("""
        <div style="text-align: center; padding: 4rem 2rem; color: #999;">
            <div style="font-size: 3rem; margin-bottom: 1rem; color: #e8aa42;">◆</div>
            <div style="font-size: 1.2rem; font-weight: 300; letter-spacing: 0.1em; margin-bottom: 1rem;">
                PROFESSIONAL FABRIC DESIGN WORKFLOW
            </div>
            <div style="font-size: 0.9rem; line-height: 1.8; max-width: 600px; margin: 0 auto;">
                Import your high-resolution design to begin the production pipeline.<br>
                Supports PNG, TIFF, and BMP formats at 300+ DPI for optimal results.
            </div>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
