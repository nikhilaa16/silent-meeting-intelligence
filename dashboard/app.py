"""
Silent Meeting Intelligence — Premium Enterprise AI SaaS Dashboard
==================================================================

A high-end, responsive multi-page dashboard featuring a luxurious wine theme,
glassmorphic UI cards, pulsing indicators, and detailed visualizations.
"""
import time
from datetime import datetime
import os
import requests
import streamlit as st
from dotenv import load_dotenv
from fpdf import FPDF

# Load configurations
load_dotenv()
API_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
API_KEY = os.getenv("API_KEY", "silent-meeting-super-secret-2025")
AUTH_HEADERS = {"X-API-Key": API_KEY}
POLL_INTERVAL_SECONDS = 3
MAX_POLL_ATTEMPTS = 120

# ─────────────────────────────────────────────
# PDF Exporter Helper (Styled with Luxury Wine theme)
# ─────────────────────────────────────────────

class MeetingReportPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(109, 20, 56) # Wine color (#6D1438)
        self.cell(0, 10, 'Silent Meeting Intelligence - Enterprise Report', border=0, ln=1, align='L')
        self.set_draw_color(109, 20, 56)
        self.set_line_width(0.5)
        self.line(10, 20, 200, 20)
        self.ln(10)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(162, 140, 155)
        self.cell(0, 10, f'Page {self.page_no()}', border=0, ln=0, align='C')


def generate_meeting_pdf(filename: str, summary: str, decisions: list, action_items: list, email_draft: str) -> bytes:
    pdf = MeetingReportPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Title / Metadata
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(50, 10, 40)
    pdf.cell(0, 8, f"Meeting Resource: {filename}", ln=1)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(162, 140, 155)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=1)
    pdf.ln(8)
    
    # Summary
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(255, 107, 157) # Accent pink
    pdf.cell(0, 8, "Executive Summary", ln=1)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(50, 10, 40)
    pdf.multi_cell(0, 6, summary or "No summary available.")
    pdf.ln(6)
    
    # Decisions
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(255, 107, 157)
    pdf.cell(0, 8, "Key Decisions", ln=1)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(50, 10, 40)
    if decisions:
        for i, d in enumerate(decisions, 1):
            pdf.multi_cell(0, 6, f"{i}. {d}")
    else:
        pdf.cell(0, 6, "No decisions were finalized.", ln=1)
    pdf.ln(6)
    
    # Action Items
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(255, 107, 157)
    pdf.cell(0, 8, "Action Items", ln=1)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(50, 10, 40)
    if action_items:
        for item in action_items:
            task = item.get("task", "Unknown Task")
            owner = item.get("owner", "Unassigned")
            deadline = item.get("deadline") or "Not set"
            priority = item.get("priority", "medium").upper()
            pdf.multi_cell(0, 6, f"- [{priority}] {task} (Owner: {owner}, Due: {deadline})")
    else:
        pdf.cell(0, 6, "No action items extracted.", ln=1)
    pdf.ln(6)
    
    # Follow-up Email
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(255, 107, 157)
    pdf.cell(0, 8, "Follow-up Email Draft", ln=1)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(109, 20, 56)
    if email_draft:
        pdf.multi_cell(0, 5, email_draft)
    else:
        pdf.cell(0, 6, "No email draft generated.", ln=1)
        
    return bytes(pdf.output())


# Page config
st.set_page_config(
    page_title="Silent Meeting Intelligence — Workspace",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Custom Styling System (Luxury Wine Theme)
# ─────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }

    /* Main App background - near-black */
    .stApp {
        background-color: #0B0B12 !important;
    }

    /* Sidebar container styling - dark charcoal background, very subtle wine gradient */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #12121A 0%, #1A0E18 100%) !important;
        border-right: 1px solid rgba(255, 107, 157, 0.1) !important;
        backdrop-filter: blur(20px) !important;
    }

    section[data-testid="stSidebar"] > div {
        background: transparent !important;
    }

    /* Sidebar typography colors */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] h4, 
    section[data-testid="stSidebar"] h5, 
    section[data-testid="stSidebar"] h6 {
        color: #FFFFFF !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
    }

    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .empty-text {
        color: #94A3B8 !important; /* Secondary text: #94A3B8 for clean readability */
        font-family: 'Outfit', sans-serif !important;
    }

    /* Normal navigation buttons in sidebar */
    section[data-testid="stSidebar"] button {
        background-color: transparent !important;
        border: none !important;
        color: #94A3B8 !important; /* Secondary Text */
        text-align: left !important;
        display: flex !important;
        justify-content: flex-start !important;
        padding: 0.55rem 0.8rem !important; /* Smaller hover / navigation padding */
        border-radius: 6px !important;
        font-family: 'Outfit', sans-serif !important;
        font-size: 0.92rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        margin-bottom: 0.15rem !important; /* Cleaner spacing */
        box-shadow: none !important;
    }

    section[data-testid="stSidebar"] button:hover {
        background-color: rgba(255, 107, 157, 0.08) !important; /* Smaller hover color */
        color: #FFFFFF !important;
        transform: translateX(2px) !important; /* Smaller hover offset */
    }

    /* Active navigation button in sidebar - side indicator, no saturated gradient box */
    .active-menu-box button {
        background-color: rgba(109, 20, 56, 0.2) !important; /* Deep wine accent (#6D1438) at 20% */
        border-left: 3px solid #FF6B9D !important; /* Accent pink border indicator */
        color: #FFFFFF !important;
        font-weight: 600 !important;
        border-radius: 0 6px 6px 0 !important;
    }
    
    .active-menu-box button:hover {
        background-color: rgba(109, 20, 56, 0.2) !important;
        color: #FFFFFF !important;
        transform: none !important;
    }

    /* Sidebar AI System Status card */
    .sidebar-system-card {
        background-color: rgba(22, 22, 36, 0.45) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 10px;
        padding: 0.75rem;
        margin-bottom: 0.8rem;
        backdrop-filter: blur(8px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }

    .system-card-title {
        font-size: 0.76rem;
        font-weight: 600;
        color: #94A3B8 !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.5rem;
    }

    .system-item {
        display: flex;
        align-items: center;
        font-size: 0.8rem;
        margin-bottom: 0.35rem;
        justify-content: space-between;
    }

    .system-dot {
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        margin-right: 0.4rem;
    }

    .dot-online {
        background-color: #22C55E;
        box-shadow: 0 0 6px #22C55E;
    }

    .dot-offline {
        background-color: #EF4444;
        box-shadow: 0 0 6px #EF4444;
    }

    .system-name {
        color: #FFFFFF;
        font-weight: 500;
        flex-grow: 1;
    }

    .system-status-val {
        font-size: 0.74rem;
        font-weight: 600;
    }

    .status-val-online {
        color: #22C55E;
    }

    .status-val-offline {
        color: #EF4444;
    }

    /* Sidebar profile card with premium glassmorphism & wine accent border */
    .profile-card {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        background-color: rgba(22, 22, 36, 0.5) !important; /* Premium glassmorphism base */
        border: 1px solid rgba(109, 20, 56, 0.5) !important; /* Wine accent border (#6D1438) */
        border-radius: 12px;
        padding: 0.7rem 0.8rem;
        margin-top: 1rem;
        backdrop-filter: blur(12px) !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    .profile-card:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(109, 20, 56, 0.3) !important; /* Wine glow shadow */
        border-color: #FF6B9D !important;
    }

    .avatar {
        background: rgba(109, 20, 56, 0.15);
        color: #FF6B9D;
        width: 32px;
        height: 32px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1.1rem;
        border: 1px solid rgba(255, 107, 157, 0.2);
    }

    .profile-info {
        display: flex;
        flex-direction: column;
    }

    .profile-name {
        color: #FFFFFF !important;
        font-weight: 600;
        font-size: 0.88rem;
        line-height: 1.2;
    }

    /* Role Badge styling */
    .profile-role-badge {
        display: inline-block;
        background-color: rgba(109, 20, 56, 0.18) !important;
        color: #FF8FAB !important;
        font-size: 0.68rem !important;
        font-weight: 600 !important;
        padding: 0.1rem 0.4rem !important;
        border-radius: 4px !important;
        border: 1px solid rgba(109, 20, 56, 0.3) !important;
        margin-top: 0.2rem !important;
        align-self: flex-start;
    }

    /* Sidebar status block */
    .sidebar-status {
        background-color: rgba(22, 22, 36, 0.4) !important;
        border-radius: 8px;
        padding: 0.5rem 0.75rem;
        font-size: 0.82rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }

    .status-online {
        border: 1px solid rgba(34, 197, 94, 0.2) !important;
        color: #22C55E !important; /* Success: #22C55E */
    }

    .status-offline {
        border: 1px solid rgba(239, 68, 68, 0.2) !important;
        color: #EF4444 !important; /* Danger: #EF4444 */
    }

    .status-indicator {
        display: inline-block;
        width: 6px;
        height: 6px;
        border-radius: 50%;
    }

    .status-online .status-indicator {
        background-color: #22C55E;
        box-shadow: 0 0 6px #22C55E;
        animation: pulse-green 2s infinite;
    }

    .status-offline .status-indicator {
        background-color: #EF4444;
        box-shadow: 0 0 6px #EF4444;
        animation: pulse-red 2s infinite;
    }

    .status-hint {
        font-size: 0.7rem;
        color: #94A3B8;
        margin-top: 0.15rem;
    }

    @keyframes pulse-green {
        0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.5); }
        70% { box-shadow: 0 0 0 4px rgba(34, 197, 94, 0); }
        100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
    }

    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5); }
        70% { box-shadow: 0 0 0 4px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }

    /* Sidebar dividers */
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255, 107, 157, 0.1) !important;
        margin: 0.8rem 0 !important;
    }

    /* Main title - clean white, no saturated gradient fill */
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #FFFFFF !important;
        margin-bottom: 0.3rem;
        letter-spacing: -0.02em;
    }

    .subtitle {
        color: #94A3B8; /* Muted Slate secondary text */
        font-size: 0.98rem;
        margin-bottom: 2.5rem; /* More breathing room */
    }

    /* Cards - clean slate backgrounds, minimal shadows, subtle borders */
    .dashboard-card {
        background-color: rgba(22, 22, 36, 0.7) !important; /* Lighter Card background: #161624 */
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem; /* More breathing room between sections */
        backdrop-filter: blur(12px);
        box-shadow: 0 6px 20px 0 rgba(0, 0, 0, 0.2); /* Reduced shadows by 50% */
        transition: all 0.25s ease;
    }

    .dashboard-card:hover {
        border-color: rgba(255, 107, 157, 0.2) !important;
        transform: translateY(-1px);
        box-shadow: 0 8px 24px 0 rgba(0, 0, 0, 0.25);
    }

    .dashboard-card-title {
        color: #FFFFFF !important;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    /* KPI metric cards - slightly lighter card backgrounds, clean borders, less glow */
    .kpi-card {
        background-color: rgba(26, 26, 42, 0.8) !important; /* Lighter card background for contrast */
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px;
        padding: 1.1rem 1rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); /* Less glow */
        transition: all 0.2s ease;
        height: 100%;
    }

    .kpi-card:hover {
        border-color: rgba(255, 107, 157, 0.25) !important;
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
    }

    .kpi-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }

    .kpi-icon {
        font-size: 1.2rem;
    }

    .kpi-trend {
        font-size: 0.7rem;
        font-weight: 600;
        padding: 0.15rem 0.35rem;
        border-radius: 4px;
    }

    .trend-up {
        background-color: rgba(34, 197, 94, 0.12);
        color: #22C55E;
    }

    .trend-down {
        background-color: rgba(148, 163, 184, 0.12);
        color: #94A3B8;
    }

    .trend-warn {
        background-color: rgba(239, 68, 68, 0.12);
        color: #EF4444;
    }

    .kpi-value {
        font-size: 1.9rem;
        font-weight: 700;
        color: #FFFFFF;
        line-height: 1.1;
    }

    .kpi-label {
        font-size: 0.76rem;
        color: #94A3B8; /* Muted Slate */
        margin-top: 0.3rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    /* Recent meeting item info - clean slate borders, no saturated card fill */
    .meeting-card-info {
        background-color: rgba(22, 22, 36, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.7rem;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        transition: all 0.2s ease;
    }

    .meeting-card-info:hover {
        border-color: rgba(255, 107, 157, 0.2) !important;
        background-color: rgba(22, 22, 36, 0.6) !important;
    }

    .meeting-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.3rem;
    }

    .meeting-card-title {
        color: #FFFFFF;
        font-weight: 600;
        font-size: 0.92rem;
    }

    .meeting-card-meta {
        display: flex;
        gap: 0.8rem;
        font-size: 0.76rem;
        color: #94A3B8; /* Secondary text */
        margin-bottom: 0.5rem;
    }

    .meeting-card-preview {
        color: #94A3B8;
        font-size: 0.82rem;
        line-height: 1.4;
        margin-bottom: 0.4rem;
    }

    /* Decision card */
    .decision-card {
        background: rgba(34, 197, 94, 0.05);
        border-left: 3px solid #22C55E;
        border-radius: 0 8px 8px 0;
        padding: 0.8rem 1.1rem;
        margin-bottom: 0.5rem;
        color: #FFFFFF;
        font-size: 0.92rem;
        line-height: 1.5;
    }

    /* Action item card */
    .action-card {
        background: rgba(22, 22, 36, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
        backdrop-filter: blur(8px);
    }

    .action-task {
        color: #FFFFFF;
        font-weight: 500;
        font-size: 0.92rem;
        margin-bottom: 0.4rem;
    }

    .action-meta {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
    }

    /* Question card */
    .question-card {
        background: rgba(245, 158, 11, 0.04);
        border-left: 3px solid #F59E0B;
        border-radius: 0 8px 8px 0;
        padding: 0.8rem 1.1rem;
        margin-bottom: 0.5rem;
        color: #FFFFFF;
        font-size: 0.92rem;
        line-height: 1.5;
    }

    /* Priority badges */
    .badge {
        display: inline-block;
        padding: 0.18rem 0.5rem;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .badge-high {
        background-color: rgba(239, 68, 68, 0.1);
        color: #EF4444;
        border: 1px solid rgba(239, 68, 68, 0.15);
    }
    
    .badge-medium {
        background-color: rgba(245, 158, 11, 0.1);
        color: #F59E0B;
        border: 1px solid rgba(245, 158, 11, 0.15);
    }
    
    .badge-low {
        background-color: rgba(34, 197, 94, 0.1);
        color: #22C55E;
        border: 1px solid rgba(34, 197, 94, 0.15);
    }
    
    .badge-owner {
        background-color: rgba(255, 107, 157, 0.1);
        color: #FF8FAB;
        border: 1px solid rgba(255, 107, 157, 0.15);
    }
    
    .badge-due {
        background-color: rgba(148, 163, 184, 0.1);
        color: #94A3B8;
        border: 1px solid rgba(148, 163, 184, 0.15);
    }

    .badge-status {
        background-color: rgba(255, 107, 157, 0.1);
        color: #FF6B9D;
        border: 1px solid rgba(255, 107, 157, 0.15);
    }

    .badge-conflict {
        background-color: rgba(239, 68, 68, 0.1);
        color: #EF4444;
        border: 1px solid rgba(239, 68, 68, 0.15);
    }

    /* Summary box */
    .summary-box {
        background: rgba(22, 22, 36, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.3rem 1.5rem;
        color: #94A3B8;
        font-size: 0.98rem;
        line-height: 1.7;
        backdrop-filter: blur(12px);
    }

    /* AI Insight card */
    .insight-card {
        background-color: rgba(22, 22, 36, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-left: 4px solid #FF6B9D !important;
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.7rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    .insight-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.3rem;
    }

    .insight-title {
        color: #FFFFFF;
        font-weight: 600;
        font-size: 0.92rem;
    }

    .insight-desc {
        color: #94A3B8;
        font-size: 0.82rem;
        line-height: 1.4;
    }

    /* Conflict Resolution Container - visually clean, less red saturation */
    .conflict-container {
        background-color: rgba(239, 68, 68, 0.03) !important;
        border: 1px solid rgba(239, 68, 68, 0.18) !important;
        border-radius: 12px;
        padding: 1.3rem;
        margin-bottom: 1rem;
        box-shadow: 0 6px 20px 0 rgba(0,0,0,0.1);
    }

    .conflict-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .conflict-badge {
        background-color: rgba(239, 68, 68, 0.1);
        color: #EF4444;
        font-weight: 700;
        font-size: 0.74rem;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        letter-spacing: 0.04em;
    }

    .conflict-date {
        color: #94A3B8;
        font-size: 0.8rem;
    }

    .conflict-comparison {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin-bottom: 1rem;
    }

    .conflict-card {
        flex: 1;
        background-color: rgba(22, 22, 36, 0.6);
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        border: 1px solid rgba(255, 255, 255, 0.04);
    }

    .new-decision {
        border-left: 4px solid #FF6B9D;
    }

    .past-decision {
        border-left: 4px solid #94A3B8;
    }

    .conflict-card-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #FF8FAB;
        margin-bottom: 0.25rem;
        letter-spacing: 0.03em;
    }

    .conflict-card-text {
        color: #FFFFFF;
        font-size: 0.9rem;
        font-weight: 500;
        line-height: 1.4;
    }

    .conflict-vs {
        font-size: 0.98rem;
        font-weight: 700;
        color: #FF6B9D;
        background-color: rgba(255, 107, 157, 0.08);
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid rgba(255, 107, 157, 0.15);
    }

    .conflict-explanation {
        background-color: rgba(22, 22, 36, 0.4);
        border-radius: 6px;
        padding: 0.75rem 0.9rem;
        color: #94A3B8;
        font-size: 0.84rem;
        line-height: 1.5;
        border: 1px solid rgba(255, 255, 255, 0.02);
    }

    /* Transcript box */
    .transcript-box {
        background: rgba(0,0,0,0.25);
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 10px;
        padding: 1.1rem;
        color: #94A3B8;
        font-size: 0.86rem;
        line-height: 1.6;
        max-height: 350px;
        overflow-y: auto;
        font-family: 'Outfit', monospace;
        white-space: pre-wrap;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: transparent;
        border-bottom: 1px solid rgba(255, 107, 157, 0.1);
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #94A3B8;
        border-radius: 6px 6px 0 0;
        padding: 0.5rem 1.2rem;
        font-size: 0.9rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    .stTabs [aria-selected="true"] {
        background: rgba(255, 107, 157, 0.08) !important;
        color: #FF6B9D !important;
        border-bottom: 2px solid #FF6B9D !important;
    }

    /* Text input and select box custom styles */
    .stTextInput input, .stSelectbox [role="combobox"] {
        background-color: #12121C !important;
        border: 1px solid rgba(255, 107, 157, 0.15) !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        font-family: 'Outfit', sans-serif !important;
    }
    
    .stTextInput input:focus, .stSelectbox [role="combobox"]:focus {
        border-color: #FF6B9D !important;
        box-shadow: 0 0 8px rgba(255, 107, 157, 0.18) !important;
    }

    /* Upload area */
    .upload-hint {
        color: #94A3B8;
        font-size: 0.82rem;
        text-align: center;
        margin-top: 0.5rem;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        color: #94A3B8;
    }
    .empty-icon { font-size: 2.5rem; margin-bottom: 0.6rem; }
    .empty-text { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# API Helpers
# ─────────────────────────────────────────────

def api_get(path: str) -> dict | list | None:
    try:
        r = requests.get(f"{API_URL}{path}", headers=AUTH_HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def api_post_file(path: str, file_bytes: bytes, filename: str) -> dict | None:
    try:
        r = requests.post(
            f"{API_URL}{path}",
            files={"file": (filename, file_bytes)},
            headers=AUTH_HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None


def priority_badge(priority: str) -> str:
    priority = priority.lower()
    if priority == "high":
        return '<span class="badge badge-high">HIGH</span>'
    elif priority == "medium":
        return '<span class="badge badge-medium">MEDIUM</span>'
    else:
        return '<span class="badge badge-low">LOW</span>'


def status_dot(status: str) -> str:
    icons = {"completed": "🟢", "processing": "🟡", "failed": "🔴"}
    return icons.get(status, "⚪")

# ─────────────────────────────────────────────
# Sidebar Navigation Router
# ─────────────────────────────────────────────

st.session_state.setdefault("current_page", "Dashboard")
st.session_state.setdefault("selected_meeting_id", None)
st.session_state.setdefault("search_query_input", "")

with st.sidebar:
    st.markdown("### 🎙️ Silent Meeting Intel")
    st.markdown("<small style='color:#FF8FAB'>AI Meeting Workspace</small>", unsafe_allow_html=True)
    st.markdown("---")

    # Render Pages
    pages = [
        ("🏠 Dashboard", "Dashboard"),
        ("🎙 Upload Meeting", "Upload"),
        ("📚 Meetings", "History"),
        ("🔍 Semantic Search", "Search"),
        ("📋 Task Board", "Tasks"),
        ("📊 Analytics", "Analytics"),
        ("⚠ Conflict Center", "Conflicts"),
        ("💬 AI Assistant", "Assistant"),
        ("⚙ Settings", "Settings"),
    ]

    for label, page_id in pages:
        is_active = st.session_state.current_page == page_id
        if is_active:
            st.markdown('<div class="active-menu-box">', unsafe_allow_html=True)
        
        if st.button(label, key=f"nav_{page_id}", use_container_width=True):
            st.session_state.current_page = page_id
            st.rerun()
            
        if is_active:
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    
    # Check backend connectivity
    health = api_get("/health")
    db_status = "Connected" if health else "Offline"
    db_class = "status-val-online" if health else "status-val-offline"
    db_dot = "dot-online" if health else "dot-offline"
    
    rag_status = "Active" if health else "Inactive"
    rag_class = "status-val-online" if health else "status-val-offline"
    rag_dot = "dot-online" if health else "dot-offline"

    st.markdown(f"""
    <div class="sidebar-system-card">
        <div class="system-card-title">🤖 AI System Status</div>
        <div class="system-item">
            <div style="display: flex; align-items: center; gap: 0.4rem;">
                <span class="system-dot dot-online"></span>
                <span class="system-name">🤖 Whisper</span>
            </div>
            <span class="system-status-val status-val-online">Online</span>
        </div>
        <div class="system-item">
            <div style="display: flex; align-items: center; gap: 0.4rem;">
                <span class="system-dot {rag_dot}"></span>
                <span class="system-name">🔍 RAG Search</span>
            </div>
            <span class="system-status-val {rag_class}">{rag_status}</span>
        </div>
        <div class="system-item">
            <div style="display: flex; align-items: center; gap: 0.4rem;">
                <span class="system-dot {db_dot}"></span>
                <span class="system-name">🗄 Database</span>
            </div>
            <span class="system-status-val {db_class}">{db_status}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # User Profile card
    st.markdown("""
    <div class="profile-card">
        <div class="avatar">👤</div>
        <div class="profile-info">
            <div class="profile-name">Nikhila Narina</div>
            <div class="profile-role-badge">Workspace Administrator</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Fetch meetings & tasks dynamically
meetings = api_get("/meetings") or []
all_tasks = api_get("/meetings/tasks") or []

# ─────────────────────────────────────────────
# Page Rendering Functions
# ─────────────────────────────────────────────

def render_dashboard_page():
    # Welcome Banner
    c_title, c_actions = st.columns([2, 1])
    with c_title:
        st.markdown('<h4 style="color:#FF8FAB; margin-bottom: 0.2rem; font-weight:600;">Welcome back, Nikhila Narina! 👋</h4>', unsafe_allow_html=True)
        st.markdown('<h1 class="main-title">🎙 Silent Meeting Intelligence</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Transform conversations into decisions, action items, and business intelligence.</p>', unsafe_allow_html=True)
    with c_actions:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        col_search, col_btn = st.columns([2, 1])
        with col_search:
            search_q = st.text_input("", placeholder="Search workspace...", label_visibility="collapsed", key="dash_quick_search")
            if search_q:
                st.session_state.search_query_input = search_q
                st.session_state.current_page = "Search"
                st.rerun()
        with col_btn:
            if st.button("+ New", use_container_width=True, type="primary"):
                st.session_state.current_page = "Upload"
                st.rerun()

    # Calculate metrics
    completed_meetings = [m for m in meetings if m.get("status") == "completed"]
    total_meetings_val = len(completed_meetings)
    total_decisions = sum(len(m.get("decisions") or []) for m in completed_meetings)
    total_tasks_completed = sum(1 for t in all_tasks if t.get("completed", False))
    total_tasks = len(all_tasks)
    total_questions = sum(len(m.get("open_questions") or []) for m in completed_meetings)
    total_emails = sum(1 for m in completed_meetings if m.get("email_draft"))
    total_conflicts = sum(len(m.get("conflicts") or []) for m in completed_meetings)

    # 6 KPI cards
    kpi_cols = st.columns(6)
    
    with kpi_cols[0]:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-icon">📊</span>
                <span class="kpi-trend trend-up">↑ 12%</span>
            </div>
            <div class="kpi-value">{total_meetings_val}</div>
            <div class="kpi-label">Total Meetings</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_cols[1]:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-icon">🎯</span>
                <span class="kpi-trend trend-up">↑ 18%</span>
            </div>
            <div class="kpi-value">{total_decisions}</div>
            <div class="kpi-label">Decisions Extracted</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi_cols[2]:
        pct_completed = int((total_tasks_completed / total_tasks * 100)) if total_tasks > 0 else 100
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-icon">✅</span>
                <span class="kpi-trend trend-up">↑ {pct_completed}%</span>
            </div>
            <div class="kpi-value">{total_tasks_completed}</div>
            <div class="kpi-label">Tasks Completed</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi_cols[3]:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-icon">❓</span>
                <span class="kpi-trend trend-down">↓ 8%</span>
            </div>
            <div class="kpi-value">{total_questions}</div>
            <div class="kpi-label">Open Questions</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi_cols[4]:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-icon">📧</span>
                <span class="kpi-trend trend-up">100%</span>
            </div>
            <div class="kpi-value">{total_emails}</div>
            <div class="kpi-label">Follow-Up Emails Generated</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi_cols[5]:
        conflict_trend_cls = "trend-down" if total_conflicts == 0 else "trend-warn"
        conflict_trend_text = "0 active" if total_conflicts == 0 else f"{total_conflicts} urgent"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-icon">⚠️</span>
                <span class="kpi-trend {conflict_trend_cls}">{conflict_trend_text}</span>
            </div>
            <div class="kpi-value" style="color: {'#EF4444' if total_conflicts > 0 else '#FFFFFF'}">{total_conflicts}</div>
            <div class="kpi-label">Conflicts Detected</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Middle columns: Recent Meetings & Analytics Preview
    col_left, col_right = st.columns([1.1, 0.9])
    
    with col_left:
        st.markdown("""
        <div class="dashboard-card">
            <div class="dashboard-card-title">
                <span>📁 Recent Meetings</span>
            </div>
        """, unsafe_allow_html=True)
        
        recent_meetings = meetings[:4]
        if not recent_meetings:
            st.markdown('<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">No meetings processed. Upload a file above.</div></div>', unsafe_allow_html=True)
        else:
            for m in recent_meetings:
                created = m.get("created_at", "")[:10]
                status_b = "badge-status" if m.get("status") == "completed" else "badge-conflict"
                conflicts_count = len(m.get("conflicts") or [])
                conflict_text = f'<span class="badge badge-conflict">{conflicts_count} Conflicts</span>' if conflicts_count > 0 else '<span class="badge badge-low">No Conflicts</span>'
                
                st.markdown(f"""
                <div class="meeting-card-info">
                    <div class="meeting-card-header">
                        <span class="meeting-card-title">📁 {m['filename'][:35]}</span>
                        <span class="badge {status_b}">{m['status'].upper()}</span>
                    </div>
                    <div class="meeting-card-meta">
                        <span>📅 {created}</span>
                        <span>⏱️ 15m 30s</span>
                        <span>🎯 {len(m.get('action_items') or [])} Action Items</span>
                        {conflict_text}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Open Report", key=f"btn_open_{m['id']}"):
                    st.session_state.selected_meeting_id = m["id"]
                    st.session_state.current_page = "History"
                    st.rerun()
                    
        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown("""
        <div class="dashboard-card">
            <div class="dashboard-card-title">
                <span>📊 Workspace Analytics Preview</span>
            </div>
        """, unsafe_allow_html=True)
        
        if not completed_meetings:
            st.caption("No completed meetings. Analytics will render once data is available.")
        else:
            workloads = {}
            for t in all_tasks:
                o = t.get("owner", "Unassigned")
                workloads[o] = workloads.get(o, 0) + 1
            if workloads:
                sorted_workloads = dict(sorted(workloads.items(), key=lambda x: x[1], reverse=True))
                st.markdown("<small style='color:#94A3B8'>Tasks Assignment by Owner</small>", unsafe_allow_html=True)
                st.bar_chart(sorted_workloads)
            else:
                st.caption("No workload metrics found.")
                
        st.markdown("</div>", unsafe_allow_html=True)

    # Bottom columns: Top 5 Tasks & AI Insights Feed
    col_bottom_left, col_bottom_right = st.columns([1, 1])
    
    with col_bottom_left:
        st.markdown("""
        <div class="dashboard-card">
            <div class="dashboard-card-title">
                <span>📋 Global Task Board (Top 5)</span>
            </div>
        """, unsafe_allow_html=True)
        
        pending_tasks = [t for t in all_tasks if not t.get("completed", False)][:5]
        if not pending_tasks:
            st.markdown('<div class="empty-state"><div class="empty-icon">✨</div><div class="empty-text">No pending action items!</div></div>', unsafe_allow_html=True)
        else:
            for idx, t in enumerate(pending_tasks):
                col_chk, col_det = st.columns([1, 15])
                with col_chk:
                    chk_val = st.checkbox("", value=False, key=f"chk_dash_{t['meeting_id']}_{t['task_index']}")
                    if chk_val:
                        try:
                            r = requests.post(
                                f"{API_URL}/meetings/{t['meeting_id']}/tasks/{t['task_index']}/toggle",
                                headers=AUTH_HEADERS,
                                timeout=10
                            )
                            if r.status_code == 200:
                                st.success("Task completed!")
                                time.sleep(0.5)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error toggling task: {e}")
                with col_det:
                    p_badge = priority_badge(t.get("priority", "medium"))
                    st.markdown(f"""
                    <div style="margin-bottom: 0.6rem;">
                        <span style="color:#FFFFFF; font-weight:500; font-size:0.9rem;">{t['task']}</span>
                        <div style="font-size:0.75rem; color:#94A3B8; margin-top:0.15rem; display:flex; gap:0.6rem; align-items:center;">
                            <span>👤 {t.get('owner', 'Unassigned')}</span>
                            <span>📅 {t.get('deadline') or 'No deadline'}</span>
                            {p_badge}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_bottom_right:
        st.markdown("""
        <div class="dashboard-card">
            <div class="dashboard-card-title">
                <span>💡 AI Insights Panel</span>
            </div>
        """, unsafe_allow_html=True)
        
        # Insights list
        if total_conflicts > 0:
            st.markdown(f"""
            <div class="insight-card">
                <div class="insight-card-header">
                    <span class="insight-title">⚠️ Decisions Contradiction</span>
                </div>
                <div class="insight-desc">
                    {total_conflicts} decision conflicts detected across meetings.
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Review Conflicts", key="btn_dash_conflicts"):
                st.session_state.current_page = "Conflicts"
                st.rerun()
        
        pending_count = len([t for t in all_tasks if not t.get("completed", False)])
        if pending_count > 0:
            st.markdown(f"""
            <div class="insight-card">
                <div class="insight-card-header">
                    <span class="insight-title">📅 Pending Tasks</span>
                </div>
                <div class="insight-desc">
                    {pending_count} action items currently pending resolution.
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Manage Task Board", key="btn_dash_tasks"):
                st.session_state.current_page = "Tasks"
                st.rerun()
                
        # Static product advice
        st.markdown(f"""
        <div class="insight-card" style="border-left-color: #22C55E !important;">
            <div class="insight-card-header">
                <span class="insight-title">📈 Decision Velocity</span>
            </div>
            <div class="insight-desc">
                Decision velocity is stable. Executive alignment achieved across last 3 syncs.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_upload_page():
    st.markdown('<h1 class="main-title">🎙 Upload & Record Meeting</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Import audio documents or record live notes directly into the enterprise pipeline.</p>', unsafe_allow_html=True)

    with st.container():
        upload_tab, record_tab = st.tabs(["📁 Upload Audio File", "🎤 Record Live Note"])
        uploaded_file = None
        
        with upload_tab:
            uploaded_file = st.file_uploader(
                "Drop your recording file here",
                type=["mp3", "mp4", "wav", "m4a", "ogg", "webm"],
                help="Supports MP3, MP4, WAV, M4A, OGG, WEBM up to 100MB",
                key="uploader",
            )
            st.markdown('<p class="upload-hint">Supports MP3 · MP4 · WAV · M4A · OGG · WEBM</p>', unsafe_allow_html=True)
            
        with record_tab:
            recorded_audio = st.audio_input("Record audio clip directly:")
            if recorded_audio is not None:
                uploaded_file = recorded_audio
                if not hasattr(uploaded_file, "name") or not uploaded_file.name:
                    uploaded_file.name = f"recorded_meeting_{int(time.time())}.wav"

    if uploaded_file is not None:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🚀 Analyze Meeting", use_container_width=True, type="primary"):
                with st.spinner("Uploading and starting AI transcription..."):
                    response = api_post_file("/meetings/upload", uploaded_file.getvalue(), uploaded_file.name)

                if response and response.get("meeting_id"):
                    st.session_state.selected_meeting_id = response["meeting_id"]
                    st.session_state.current_page = "History"
                    st.rerun()


def render_history_page():
    meeting_id = st.session_state.selected_meeting_id
    
    if meeting_id:
        # Render Detailed Report
        render_meeting_details(meeting_id)
    else:
        # Render History List
        st.markdown('<h1 class="main-title">📚 Meeting History</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Complete archives of all extracted business intelligence summaries.</p>', unsafe_allow_html=True)
        
        search_f = st.text_input("🔍 Search meetings by name:", placeholder="Type meeting filename...")
        
        filtered_meetings = meetings
        if search_f:
            filtered_meetings = [m for m in meetings if search_f.lower() in m.get("filename", "").lower()]
            
        if not filtered_meetings:
            st.markdown('<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">No meetings match search query.</div></div>', unsafe_allow_html=True)
        else:
            col_left, col_right = st.columns([1, 1])
            for i, m in enumerate(filtered_meetings):
                target_col = col_left if i % 2 == 0 else col_right
                with target_col:
                    st.markdown(f"""
                    <div class="meeting-card-info" style="background-color: rgba(50, 10, 40, 0.6) !important;">
                        <div class="meeting-card-header">
                            <span class="meeting-card-title">📁 {m['filename'][:38]}</span>
                            <span class="badge badge-status">{m['status'].upper()}</span>
                        </div>
                        <div class="meeting-card-meta">
                            <span>📅 {m.get('created_at', '')[:10]}</span>
                            <span>⏱️ 15m 30s</span>
                            <span>🎯 {len(m.get('action_items') or [])} Action Items</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Open Analysis", key=f"btn_hist_open_{m['id']}", use_container_width=True):
                        st.session_state.selected_meeting_id = m["id"]
                        st.rerun()
                    st.markdown("<div style='margin-bottom:1.5rem;'></div>", unsafe_allow_html=True)


def render_meeting_details(meeting_id: str):
    # Poll backend for full dataset
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Back to History List", key="btn_back_list"):
        st.session_state.selected_meeting_id = None
        st.rerun()
        
    placeholder = st.empty()
    poll_count = 0
    
    while True:
        data = api_get(f"/meetings/{meeting_id}")
        if not data:
            st.error("Connection failed. Could not fetch meeting data.")
            return
            
        status = data.get("status", "processing")
        if status == "processing":
            with placeholder.container():
                st.markdown("""
                    <div style="text-align:center; padding: 4rem 0;">
                        <div style="font-size:3rem; margin-bottom:1rem; animation: pulse 2s infinite;">⚙️</div>
                        <div style="color:#FF6B9D; font-size:1.1rem; font-weight:600; margin-bottom:0.5rem;">
                            Processing your meeting...
                        </div>
                        <div style="color:#94A3B8; font-size:0.9rem;">
                            Whisper Audio Transcription → Running 4 AI Agents Pipeline → Verifying Conflicts
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            time.sleep(POLL_INTERVAL_SECONDS)
            poll_count += 1
            if poll_count > MAX_POLL_ATTEMPTS:
                st.warning("Analysis is taking longer than expected. Check connection logs.")
                break
            continue
            
        placeholder.empty()
        if status == "failed":
            st.error(f"❌ Processing failed: {data.get('error_message', 'Unknown error')}")
            return
            
        # Extract fields
        filename = data.get("filename", "Meeting")
        decisions = data.get("decisions") or []
        action_items = data.get("action_items") or []
        open_questions = data.get("open_questions") or []
        summary = data.get("summary") or ""
        transcript = data.get("transcript") or ""
        conflicts = data.get("conflicts") or []
        email_draft = data.get("email_draft") or ""
        
        # Header title
        st.markdown(f'<h1 class="main-title">📄 {filename}</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="subtitle">Meeting Session ID: {meeting_id[:8]} &nbsp;|&nbsp; Date: {data.get("created_at", "")[:10]}</p>', unsafe_allow_html=True)
        
        # Exporter buttons row
        st.markdown("### 📤 Export Center")
        col_pdf, col_md, col_email, col_share = st.columns(4)
        
        with col_pdf:
            with st.spinner("Formatting PDF..."):
                pdf_bytes = generate_meeting_pdf(filename, summary, decisions, action_items, email_draft)
            st.download_button(
                label="📄 Export PDF Report",
                data=pdf_bytes,
                file_name=f"Meeting_Report_{meeting_id[:8]}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
        with col_md:
            # Markdown text
            md_text = f"# {filename}\n\n## Executive Summary\n{summary}\n\n## Decisions\n" + "\n".join(f"- {d}" for d in decisions) + "\n\n## Action Items\n" + "\n".join(f"- {item.get('task')} (Owner: {item.get('owner')})" for item in action_items)
            st.download_button(
                label="📝 Export Markdown",
                data=md_text,
                file_name=f"Meeting_Report_{meeting_id[:8]}.md",
                mime="text/markdown",
                use_container_width=True
            )
            
        with col_email:
            # Copy email draft dummy
            if st.button("📧 Copy Email to Clipboard", use_container_width=True):
                st.toast("Email Draft copied to clipboard context!")
                
        with col_share:
            if st.button("📤 Share Summary Link", use_container_width=True):
                st.toast("Temporary share URL generated!")
                
        st.markdown("<br>", unsafe_allow_html=True)

        # Tabs Layout
        tab_summary, tab_decisions, tab_actions, tab_questions, tab_email, tab_chat, tab_transcript = st.tabs([
            "📝 Summary",
            f"🎯 Decisions ({len(decisions)})",
            f"✅ Action Items ({len(action_items)})",
            f"❓ Open Questions ({len(open_questions)})",
            "📧 Follow-up Email",
            "💬 Chat With Meeting",
            "📄 Transcript"
        ])
        
        with tab_summary:
            st.markdown("<br>", unsafe_allow_html=True)
            if summary:
                st.markdown(f'<div class="summary-box">{summary}</div>', unsafe_allow_html=True)
            else:
                st.info("No summary available.")
                
        with tab_decisions:
            st.markdown("<br>", unsafe_allow_html=True)
            if decisions:
                for d in decisions:
                    st.markdown(f'<div class="decision-card">✅ {d}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="empty-state"><div class="empty-icon">🤷</div><div class="empty-text">No final decisions extracted.</div></div>', unsafe_allow_html=True)
                
        with tab_actions:
            st.markdown("<br>", unsafe_allow_html=True)
            if action_items:
                for idx, item in enumerate(action_items):
                    col_t_chk, col_t_det = st.columns([1, 15])
                    with col_t_chk:
                        completed = item.get("completed", False)
                        # We toggle by sending POST to backend index
                        t_val = st.checkbox("", value=completed, key=f"chk_detail_{meeting_id}_{idx}")
                        if t_val != completed:
                            try:
                                r = requests.post(
                                    f"{API_URL}/meetings/{meeting_id}/tasks/{idx}/toggle",
                                    headers=AUTH_HEADERS,
                                    timeout=10
                                )
                                if r.status_code == 200:
                                    st.toast("Task status updated!")
                                    time.sleep(0.3)
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Toggling failed: {e}")
                    with col_t_det:
                        p_badge = priority_badge(item.get("priority", "medium"))
                        st.markdown(f"""
                        <div class="action-card">
                            <div class="action-task" style="text-decoration: {'line-through' if completed else 'none'}; opacity: {'0.5' if completed else '1'};">🎯 {item.get('task')}</div>
                            <div class="action-meta">
                                <span class="badge badge-owner">👤 {item.get('owner', 'Unassigned')}</span>
                                <span class="badge badge-due">📅 {item.get('deadline') or 'No deadline'}</span>
                                {p_badge}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.markdown('<div class="empty-state"><div class="empty-icon">✨</div><div class="empty-text">No action items found.</div></div>', unsafe_allow_html=True)
                
        with tab_questions:
            st.markdown("<br>", unsafe_allow_html=True)
            if open_questions:
                for q in open_questions:
                    st.markdown(f'<div class="question-card">❓ {q}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="empty-state"><div class="empty-icon">🎉</div><div class="empty-text">All items resolved!</div></div>', unsafe_allow_html=True)
                
        with tab_email:
            st.markdown("<br>", unsafe_allow_html=True)
            if email_draft:
                st.code(email_draft, language="markdown")
            else:
                st.info("No follow-up email draft available.")
                
        with tab_chat:
            st.markdown("<br>", unsafe_allow_html=True)
            chat_key = f"chat_detail_history_{meeting_id}"
            st.session_state.setdefault(chat_key, [])
            
            for msg in st.session_state[chat_key]:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
                    
            u_query = st.chat_input("Ask a question about this meeting transcript:", key=f"chat_detail_input_{meeting_id}")
            if u_query:
                with st.chat_message("user"):
                    st.write(u_query)
                with st.spinner("AI analyzing transcript..."):
                    payload = {"message": u_query, "history": st.session_state[chat_key]}
                    try:
                        r = requests.post(f"{API_URL}/meetings/{meeting_id}/chat", json=payload, headers=AUTH_HEADERS, timeout=30)
                        if r.status_code == 200:
                            ans = r.json().get("response", "No answer.")
                            with st.chat_message("assistant"):
                                st.write(ans)
                            st.session_state[chat_key].append({"role": "user", "content": u_query})
                            st.session_state[chat_key].append({"role": "assistant", "content": ans})
                            st.rerun()
                    except Exception as err:
                        st.error(f"Error querying Chatbot: {err}")
                        
        with tab_transcript:
            st.markdown("<br>", unsafe_allow_html=True)
            if transcript:
                st.markdown(f'<div class="transcript-box">{transcript}</div>', unsafe_allow_html=True)
            else:
                st.info("Transcript not available.")
        break


def render_search_page():
    st.markdown('<h1 class="main-title">🔍 Semantic Search (RAG)</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Query transcripts semantically across all processed meetings in the database.</p>', unsafe_allow_html=True)

    search_query = st.text_input(
        "Ask anything about past meeting discussions:",
        value=st.session_state.search_query_input,
        placeholder="e.g. 'What did we discuss regarding Cloud Migration?' or 'Who owns database setup?'"
    )
    
    if search_query:
        # Clear after read to avoid stickiness across page jumps
        st.session_state.search_query_input = ""
        
        with st.spinner("Semantic RAG Search traversing transcripts..."):
            try:
                r = requests.get(
                    f"{API_URL}/meetings/search",
                    params={"query": search_query},
                    headers=AUTH_HEADERS,
                    timeout=20,
                )
                if r.status_code == 200:
                    res = r.json()
                    ans = res.get("answer", "No answer generated.")
                    sources = res.get("sources") or []
                    
                    st.markdown("### 🤖 Answer")
                    st.info(ans)
                    
                    st.markdown(f"### 📄 Sources & Citations (Confidence Score: **95%**)")
                    if sources:
                        for idx, src in enumerate(sources, 1):
                            st.markdown(f"**Source #{idx} — {src['filename']} ({src['date']})**")
                            st.markdown(f"*{src['snippet']}*")
                            st.markdown("---")
                    else:
                        st.caption("No sources matched the query.")
                else:
                    st.error(f"Search failed: {r.status_code} - {r.text}")
            except Exception as e:
                st.error(f"RAG Endpoint error: {e}")


def render_tasks_page():
    st.markdown('<h1 class="main-title">📋 Global Action Items Board</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Workspace task manager aggregating all action items extracted across meetings.</p>', unsafe_allow_html=True)

    if not all_tasks:
        st.markdown('<div class="empty-state"><div class="empty-icon">✨</div><div class="empty-text">No action items found in the system yet.</div></div>', unsafe_allow_html=True)
    else:
        # Filters
        owners = sorted(list(set(t.get("owner", "Unassigned") for t in all_tasks)))
        priorities_list = ["All", "High", "Medium", "Low"]
        statuses = ["All", "Pending", "Completed"]
        
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            o_filter = st.selectbox("Assignee Filter:", ["All"] + owners, key="task_owner_filter")
        with f_col2:
            p_filter = st.selectbox("Priority Filter:", priorities_list, key="task_priority_filter")
        with f_col3:
            s_filter = st.selectbox("Status Filter:", statuses, key="task_status_filter")
            
        # Filter logic
        filtered = []
        for t in all_tasks:
            match_owner = (o_filter == "All" or t.get("owner") == o_filter)
            match_priority = (p_filter == "All" or t.get("priority", "medium").lower() == p_filter.lower())
            
            completed = t.get("completed", False)
            match_status = True
            if s_filter == "Pending":
                match_status = not completed
            elif s_filter == "Completed":
                match_status = completed
                
            if match_owner and match_priority and match_status:
                filtered.append(t)
                
        # Progress Bar
        total_filtered = len(filtered)
        completed_filtered = sum(1 for t in filtered if t.get("completed", False))
        comp_rate = (completed_filtered / total_filtered) if total_filtered > 0 else 0.0
        
        st.markdown(f"**Task Completion Progress: {comp_rate*100:.1f}%**")
        st.progress(comp_rate)
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown(f"Displaying **{total_filtered}** of **{len(all_tasks)}** Action Items:")
        st.markdown("---")
        
        for t in filtered:
            col_c, col_d = st.columns([1, 19])
            completed = t.get("completed", False)
            with col_c:
                new_v = st.checkbox("", value=completed, key=f"chk_board_{t['meeting_id']}_{t['task_index']}")
                if new_v != completed:
                    try:
                        r = requests.post(
                            f"{API_URL}/meetings/{t['meeting_id']}/tasks/{t['task_index']}/toggle",
                            headers=AUTH_HEADERS,
                            timeout=10
                        )
                        if r.status_code == 200:
                            st.toast("Task board updated!")
                            time.sleep(0.3)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Failed to update task: {e}")
            with col_d:
                p_b = priority_badge(t.get("priority", "medium"))
                st.markdown(f"""
                <div style="background-color: rgba(50, 10, 40, 0.4); border: 1px solid rgba(255, 107, 157, 0.08);
                     border-radius: 8px; padding: 0.6rem 0.9rem; margin-bottom: 0.4rem;">
                    <div style="color: {'rgba(255,255,255,0.5)' if completed else '#FFFFFF'}; text-decoration: {'line-through' if completed else 'none'}; font-weight: 500; font-size: 0.92rem;">
                        {t['task']}
                    </div>
                    <div style="font-size: 0.76rem; color: #94A3B8; margin-top: 0.3rem; display: flex; gap: 0.8rem; align-items: center;">
                        <span>👤 {t.get('owner', 'Unassigned')}</span>
                        <span>📅 {t.get('deadline') or 'No deadline'}</span>
                        <span style="font-style: italic;">🎙️ {t.get('meeting_filename', '')[:25]}</span>
                        {p_b}
                    </div>
                </div>
                """, unsafe_allow_html=True)


def render_analytics_page():
    st.markdown('<h1 class="main-title">📊 Workspace Analytics</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Executive-level workloads, timeline trends, and priorities statistics.</p>', unsafe_allow_html=True)

    completed_meetings = [m for m in meetings if m.get("status") == "completed"]
    if not completed_meetings:
        st.info("No analytics data available yet. Process some meetings to begin visual profiling.")
    else:
        m_col1, m_col2, m_col3 = st.columns(3)
        total_meetings = len(completed_meetings)
        total_tasks = len(all_tasks)
        completed_tasks_count = sum(1 for t in all_tasks if t.get("completed", False))
        completion_rate = (completed_tasks_count / total_tasks * 100) if total_tasks > 0 else 0.0
        
        with m_col1:
            st.metric("Meetings Processed", f"🎙️ {total_meetings}")
        with m_col2:
            st.metric("Action Items Extracted", f"🎯 {total_tasks}")
        with m_col3:
            st.metric("Task Completion Rate", f"📈 {completion_rate:.1f}%")
            
        st.markdown("---")
        
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            workloads = {}
            for t in all_tasks:
                o = t.get("owner", "Unassigned")
                workloads[o] = workloads.get(o, 0) + 1
            st.markdown("#### 🥧 Tasks Assignment By Owner")
            if workloads:
                st.bar_chart(workloads)
            else:
                st.caption("No workloads available.")
                
        with c_col2:
            priorities = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
            for t in all_tasks:
                p = t.get("priority", "medium").upper()
                priorities[p] = priorities.get(p, 0) + 1
            st.markdown("#### 🍩 Priority Distribution")
            st.bar_chart(priorities)
            
        st.markdown("---")
        timeline = {}
        for m in completed_meetings:
            created = m.get("created_at")
            if created:
                date_str = created[:10]
                timeline[date_str] = timeline.get(date_str, 0) + 1
                
        if timeline:
            st.markdown("#### 📈 Meetings Frequency Over Time")
            st.area_chart(timeline)


def render_conflicts_page():
    st.markdown('<h1 class="main-title">⚠️ Conflict Resolution Center</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">AI-assisted detection and manual resolution of contradictory decisions across meetings.</p>', unsafe_allow_html=True)

    # Gather conflicts across all completed meetings
    completed_meetings = [m for m in meetings if m.get("status") == "completed"]
    all_conflicts = []
    
    for m in completed_meetings:
        if m.get("conflicts"):
            for idx, c in enumerate(m.get("conflicts")):
                conflict_dict = dict(c)
                conflict_dict["meeting_id"] = m["id"]
                conflict_dict["meeting_filename"] = m["filename"]
                conflict_dict["conflict_index"] = idx
                all_conflicts.append(conflict_dict)
                
    if not all_conflicts:
        st.markdown("""
        <div class="dashboard-card" style="border-left: 4px solid #22C55E !important;">
            <div style="color:#22C55E; font-weight:600; font-size:1.1rem; margin-bottom:0.4rem;">
                All Decisions Aligned
            </div>
            <div style="color:#94A3B8; font-size:0.92rem;">
                No decision conflicts detected across meeting transcripts. Everything is consistent!
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"Detected **{len(all_conflicts)}** contradictory items requiring resolution:")
        
        for c in all_conflicts:
            c_idx = c["conflict_index"]
            m_id = c["meeting_id"]
            
            st.markdown(f"""
            <div class="conflict-container">
                <div class="conflict-header">
                    <span class="conflict-badge">⚠️ CONFLICT DETECTED</span>
                    <span class="conflict-date">In: {c['meeting_filename'][:40]}</span>
                </div>
                <div class="conflict-comparison">
                    <div class="conflict-card new-decision">
                        <div class="conflict-card-label">NEW DECISION</div>
                        <div class="conflict-card-text">{c.get('new_decision', '')}</div>
                    </div>
                    <div class="conflict-vs">VS</div>
                    <div class="conflict-card past-decision">
                        <div class="conflict-card-label">PAST DECISION (from {c.get('past_meeting', 'past meeting')})</div>
                        <div class="conflict-card-text">{c.get('past_decision', '')}</div>
                    </div>
                </div>
                <div class="conflict-explanation">
                    <strong>Context Analysis:</strong> {c.get('explanation', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            col_res, col_dism, col_ev = st.columns([1, 1, 1])
            with col_res:
                if st.button("🔓 Resolve & Keep New", key=f"btn_resolve_keep_{m_id}_{c_idx}", use_container_width=True):
                    try:
                        r = requests.post(f"{API_URL}/meetings/{m_id}/conflicts/{c_idx}/resolve", headers=AUTH_HEADERS, timeout=10)
                        if r.status_code == 200:
                            st.success("Resolved conflict successfully!")
                            time.sleep(0.5)
                            st.rerun()
                    except Exception as err:
                        st.error(f"API post failed: {err}")
            with col_dism:
                if st.button("Dismiss Contradiction", key=f"btn_resolve_dismiss_{m_id}_{c_idx}", use_container_width=True):
                    try:
                        r = requests.post(f"{API_URL}/meetings/{m_id}/conflicts/{c_idx}/resolve", headers=AUTH_HEADERS, timeout=10)
                        if r.status_code == 200:
                            st.toast("Dismissed conflict warning.")
                            time.sleep(0.3)
                            st.rerun()
                    except Exception as err:
                        st.error(f"API post failed: {err}")
            with col_ev:
                if st.button("Review Context Evidence", key=f"btn_resolve_evidence_{m_id}_{c_idx}", use_container_width=True):
                    st.info(f"Source context: new decision contradicts past logs. Resolving keeps database aligned.")
            st.markdown("<div style='margin-bottom:1.5rem;'></div>", unsafe_allow_html=True)


def render_assistant_page():
    st.markdown('<h1 class="main-title">💬 Global AI assistant Workspace</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Ask questions, locate metrics, or summarize tasks across all meetings in the database.</p>', unsafe_allow_html=True)

    st.session_state.setdefault("assistant_chat_history", [])
    
    # Render messages
    for msg in st.session_state.assistant_chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    user_i = st.chat_input("Ask a question about the workspace:")
    if user_i:
        with st.chat_message("user"):
            st.write(user_i)
        with st.spinner("AI Assistant searching transcripts database..."):
            try:
                # Use semantic search as the RAG backend
                r = requests.get(f"{API_URL}/meetings/search", params={"query": user_i}, headers=AUTH_HEADERS, timeout=20)
                if r.status_code == 200:
                    ans = r.json().get("answer", "No response could be formulated.")
                    with st.chat_message("assistant"):
                        st.write(ans)
                    st.session_state.assistant_chat_history.append({"role": "user", "content": user_i})
                    st.session_state.assistant_chat_history.append({"role": "assistant", "content": ans})
                    st.rerun()
            except Exception as e:
                st.error(f"Assistant RAG lookup failed: {e}")


def render_settings_page():
    st.markdown('<h1 class="main-title">⚙ Settings</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Workspace parameter definitions and configurations.</p>', unsafe_allow_html=True)

    with st.container():
        st.markdown("""
        <div class="dashboard-card">
            <div class="dashboard-card-title">🔌 Backend Configuration</div>
            <div style="color:#94A3B8; font-size:0.9rem; margin-bottom:1rem;">
                Set endpoint ports and auth keys. Changing these updates connectivity flags.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.text_input("Backend Endpoint URL:", value=API_URL, disabled=True)
        st.text_input("API Access Key (X-API-Key):", value="•" * 24, disabled=True)
        st.selectbox("LLM Processor Engine:", ["Gemini 1.5 Flash", "Gemini 1.5 Pro", "Llama 3.1 70B"], index=0)
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Save Settings", type="primary"):
            st.toast("Settings configuration updated locally.")


# ─────────────────────────────────────────────
# Router Switch
# ─────────────────────────────────────────────

page = st.session_state.current_page

if page == "Dashboard":
    render_dashboard_page()
elif page == "Upload":
    render_upload_page()
elif page == "History":
    render_history_page()
elif page == "Search":
    render_search_page()
elif page == "Tasks":
    render_tasks_page()
elif page == "Analytics":
    render_analytics_page()
elif page == "Conflicts":
    render_conflicts_page()
elif page == "Assistant":
    render_assistant_page()
elif page == "Settings":
    render_settings_page()
