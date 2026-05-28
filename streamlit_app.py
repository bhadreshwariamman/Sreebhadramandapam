import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, date, timedelta
import uuid
from fpdf import FPDF
import io
import base64
from barcode import Code128
from barcode.writer import ImageWriter
from PIL import Image
import urllib.parse

st.set_page_config(
    page_title="Sree Bhadra Mandapam",
    page_icon="🛕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== SUPABASE INIT ====================
@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase: Client = get_supabase()

# ==================== HELPERS ====================
def generate_id(prefix: str, table: str) -> str:
    try:
        res = supabase.table(table).select("id").order("id", desc=True).limit(1).execute()
        if res.data:
            last = res.data[0]["id"]
            num = int(last[len(prefix):]) + 1
            return f"{prefix}{num:03d}"
    except Exception:
        pass
    return f"{prefix}001"

def fmt_currency(val):
    return f"₹{val:,.2f}" if val else "₹0.00"

def fmt_date(d):
    if not d:
        return "-"
    if isinstance(d, str):
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d-%m-%Y")
    return d.strftime("%d-%m-%Y")

def get_setting(key: str) -> str:
    try:
        res = supabase.table("app_settings").select("value").eq("key", key).execute()
        if res.data:
            return res.data[0]["value"]
    except Exception:
        pass
    return ""

def set_setting(key: str, value: str):
    try:
        existing = supabase.table("app_settings").select("id").eq("key", key).execute().data
        if existing:
            supabase.table("app_settings").update({"value": value}).eq("key", key).execute()
        else:
            supabase.table("app_settings").insert({"key": key, "value": value}).execute()
    except Exception as e:
        st.error(f"Setting save failed: {e}")

def get_expense_categories():
    try:
        res = supabase.table("expense_categories").select("name").order("name").execute()
        return [r["name"] for r in res.data] if res.data else ["Maintenance", "Staff", "Utilities", "Decoration", "Other"]
    except Exception:
        return ["Maintenance", "Staff", "Utilities", "Decoration", "Other"]

def format_whatsapp_number(phone: str) -> str:
    digits = ''.join(c for c in phone if c.isdigit())
    if digits.startswith('0'):
        digits = digits[1:]
    if not digits.startswith('91'):
        digits = '91' + digits
    return digits

def get_whatsapp_link(phone: str, inv_id: str, amount: float):
    clean = format_whatsapp_number(phone)
    msg = (f"Greetings from Sree Bhadra Mandapam!\n\n"
           f"Your invoice *{inv_id}* has been generated.\n"
           f"Total Amount: Rs.{amount:,.2f}\n"
           f"Status: PAID IN FULL\n\n"
           f"Thank you for choosing us.\n"
           f"Kanjampuram P O, Kanniyakumari Dist - 629154")
    encoded = urllib.parse.quote(msg)
    return f"https://wa.me/{clean}?text={encoded}"

# ==================== BARCODE ====================
def generate_barcode(asset_id: str):
    buffer = io.BytesIO()
    barcode = Code128(asset_id, writer=ImageWriter())
    barcode.write(buffer, options={"write_text": True, "text_distance": 2, "quiet_zone": 2})
    buffer.seek(0)
    return buffer

# ==================== PDF GENERATORS ====================
class InvoicePDF(FPDF):
    def header(self):
        self.set_fill_color(139, 21, 56)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, "Sree Bhadra Mandapam", ln=True, align="C", fill=True)
        self.set_font("Arial", "", 9)
        self.cell(0, 5, "Samrakshana Seva Trust 179/2004", ln=True, align="C", fill=True)
        self.cell(0, 5, "Kanjampuram P O, Kanniyakumari Dist - 629154", ln=True, align="C", fill=True)
        self.cell(0, 5, "Mobile: 9659828283 | bhadreshwariamman@gmail.com", ln=True, align="C", fill=True)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def generate_invoice_pdf(inv, bk, payments):
    pdf = InvoicePDF()
    pdf.add_page()

    pdf.set_text_color(139, 21, 56)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"TAX INVOICE - {inv['id']}", ln=True, align="C")
    pdf.set_draw_color(184, 134, 11)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"Invoice Date: {fmt_date(inv.get('invoice_date'))}", ln=True)
    pdf.cell(0, 8, f"Booking Ref: {inv['booking_id']}", ln=True)
    pdf.cell(0, 8, f"Customer: {bk.get('customer_name', '-')}", ln=True)
    pdf.cell(0, 8, f"Phone: {bk.get('phone', '-')}", ln=True)
    pdf.cell(0, 8, f"Event: {bk.get('event_name', '-')}", ln=True)
    pdf.cell(0, 8, f"Hall: {bk.get('hall_name', '-')}", ln=True)
    pdf.cell(0, 8, f"Address: {bk.get('address', '-')}", ln=True)
    pdf.ln(4)

    pdf.set_fill_color(255, 251, 245)
    pdf.set_font("Arial", "B", 10)
    pdf.set_draw_color(184, 134, 11)
    pdf.cell(50, 10, "Payment Date", 1, 0, "C", True)
    pdf.cell(50, 10, "Method", 1, 0, "C", True)
    pdf.cell(90, 10, "Amount (Rs.)", 1, 1, "C", True)

    pdf.set_font("Arial", "", 10)
    for p in payments:
        pdf.cell(50, 10, fmt_date(p.get('payment_date')), 1, 0, "C")
        pdf.cell(50, 10, p.get('method', '-'), 1, 0, "C")
        pdf.cell(90, 10, f"{p.get('amount', 0):,.2f}", 1, 1, "R")

    pdf.ln(6)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Total Amount: Rs.{inv.get('total_amount', 0):,.2f}", ln=True, align="R")
    pdf.cell(0, 10, f"Total Paid: Rs.{inv.get('total_paid', 0):,.2f}", ln=True, align="R")
    pdf.set_text_color(46, 125, 50)
    pdf.cell(0, 10, f"Status: PAID IN FULL", ln=True, align="R")
    pdf.set_text_color(139, 21, 56)
    pdf.set_font("Arial", "I", 9)
    pdf.ln(8)
    pdf.cell(0, 8, "This is a computer generated invoice.", ln=True, align="C")

    buffer = io.BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

class ReportPDF(FPDF):
    def header(self):
        self.set_fill_color(139, 21, 56)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Sree Bhadra Mandapam - Report", ln=True, align="C", fill=True)
        self.ln(4)
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def generate_report_pdf(title: str, df: pd.DataFrame):
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(139, 21, 56)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(4)

    if df.empty:
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 10, "No data available for selected range.", ln=True, align="C")
    else:
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(255, 251, 245)
        pdf.set_draw_color(184, 134, 11)
        col_width = 190 / len(df.columns)
        for col in df.columns:
            pdf.cell(col_width, 10, str(col)[:20], 1, 0, "C", True)
        pdf.ln()

        pdf.set_font("Arial", "", 9)
        pdf.set_fill_color(255, 255, 255)
        for _, row in df.iterrows():
            for val in row:
                text = str(val)[:25] if val is not None else "-"
                pdf.cell(col_width, 8, text, 1, 0, "L")
            pdf.ln()

    buffer = io.BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# ==================== AUTH ====================
def login_page():
    # Inject custom CSS for full-screen divine login
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    .stApp {
        background: linear-gradient(135deg, #1a0208 0%, #5a0f26 30%, #8B1538 60%, #B8860B 100%);
    }
    [data-testid="stSidebar"] {display: none !important;}
    [data-testid="collapsedControl"] {display: none !important;}
    .block-container {
        max-width: 100% !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    @keyframes rotate {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    @keyframes pulse {
        0%, 100% { opacity: 0.6; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.05); }
    }
    .divine-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        min-height: 100vh;
        padding-top: 20px;
        padding-bottom: 20px;
    }
    .divine-title {
        color: #FFD700;
        font-family: Georgia, 'Times New Roman', serif;
        text-align: center;
        text-shadow: 0 3px 10px rgba(0,0,0,0.8);
        margin-bottom: 2px;
        letter-spacing: 1px;
    }
    .divine-sub {
        color: #FFF8DC;
        text-align: center;
        font-size: 1rem;
        text-shadow: 0 2px 6px rgba(0,0,0,0.7);
        margin-bottom: 2px;
    }
    .divine-contact {
        color: #E8DCC4;
        text-align: center;
        font-size: 0.82rem;
        text-shadow: 0 1px 4px rgba(0,0,0,0.6);
        margin-bottom: 2px;
    }
    .rays-box {
        position: relative;
        width: 200px;
        height: 200px;
        margin: 15px auto 25px auto;
    }
    .rays {
        position: absolute;
        inset: -30px;
        border-radius: 50%;
        background: repeating-conic-gradient(
            from 0deg,
            rgba(255, 215, 0, 0.12) 0deg 5deg,
            transparent 5deg 10deg
        );
        animation: rotate 25s linear infinite;
    }
    .rays-glow {
        position: absolute;
        inset: -8px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,215,0,0.3) 0%, transparent 60%);
        animation: pulse 3s ease-in-out infinite;
    }
    .god-frame {
        position: absolute;
        inset: 0;
        border-radius: 50%;
        border: 4px solid #FFD700;
        box-shadow: 0 0 40px rgba(255, 215, 0, 0.5), inset 0 0 20px rgba(255, 215, 0, 0.2);
        overflow: hidden;
        background: #2E0410;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10;
    }
    .god-frame img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .login-form-wrapper {
        background: rgba(255, 251, 245, 0.98);
        border-radius: 18px;
        padding: 28px 32px;
        border: 3px solid #B8860B;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        max-width: 420px;
        width: 90%;
        margin: 0 auto;
    }
    </style>
    """, unsafe_allow_html=True)

    # Get stored login image URL
    img_url = ""
    try:
        res = supabase.table("app_settings").select("value").eq("key", "login_image_url").execute()
        if res.data:
            img_url = res.data[0]["value"]
    except Exception:
        pass

    # Build the divine header
    st.markdown("""
    <div class="divine-container">
        <div class="divine-title" style="font-size: 2.2rem; font-weight: bold;">Sree Bhadra Mandapam</div>
        <div class="divine-sub">Samrakshana Seva Trust 179/2004</div>
        <div class="divine-contact">Kanjampuram P O, Kanniyakumari Dist - 629154</div>
        <div class="divine-contact">Mobile No: 9659828283 | E-mail: bhadreshwariamman@gmail.com</div>
        <div class="rays-box">
            <div class="rays"></div>
            <div class="rays-glow"></div>
            <div class="god-frame">
    """, unsafe_allow_html=True)

    # FIX: Use st.image instead of raw HTML to avoid quote escaping issues
    if img_url:
        try:
            st.image(img_url, width=200, use_container_width=False)
        except Exception:
            st.markdown('<div style="font-size:4rem; color:#FFD700; text-align:center; line-height:1;">🛕<br><span style="font-size:0.8rem; color:#FFF8DC;">Bhadreshwariamman</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:4rem; color:#FFD700; text-align:center; line-height:1;">🛕<br><span style="font-size:0.8rem; color:#FFF8DC;">Bhadreshwariamman</span></div>', unsafe_allow_html=True)

    st.markdown("""
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Login form - NO columns, direct centered wrapper
    st.markdown('<div class="login-form-wrapper">', unsafe_allow_html=True)

    st.markdown("<h3 style='text-align:center; color:#8B1538; margin-bottom:20px; font-family:Georgia,serif;'>Management Login</h3>", unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", value="admin", placeholder="👤 Enter username")
        password = st.text_input("Password", type="password", value="admin", placeholder="🔒 Enter password")
        submitted = st.form_submit_button("✨ Sign In", use_container_width=True, type="primary")

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password")
            else:
                try:
                    res = supabase.table("users").select("*").eq("username", username).eq("password_hash", password).execute()
                    if res.data:
                        st.session_state.authenticated = True
                        st.session_state.user = res.data[0]
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Use admin / admin")
                except Exception as e:
                    st.error(f"Database connection error: {e}")

    st.markdown("<p style='text-align:center; color:#8B1538; font-size:0.85rem; margin-top:12px;'>🙏 Welcome to Sree Bhadra Mandapam</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
def do_logout():
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

# ==================== SIDEBAR ====================
def sidebar_nav():
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2E0410 0%, #5a0f26 50%, #8B1538 100%) !important;
    }
    [data-testid="stSidebar"] .css-1d391kg,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #FFD700 !important;
    }
    [data-testid="stSidebar"] button {
        background: transparent !important;
        border: 1px solid rgba(255,215,0,0.25) !important;
        color: #FFE082 !important;
        border-radius: 12px !important;
        margin-bottom: 6px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    [data-testid="stSidebar"] button:hover {
        background: rgba(184,134,11,0.25) !important;
        border-color: #FFD700 !important;
        transform: translateX(6px) !important;
        box-shadow: 0 4px 12px rgba(255,215,0,0.2) !important;
    }
    [data-testid="stSidebar"] button[kind="primary"] {
        background: linear-gradient(90deg, #B8860B, #FFD700) !important;
        color: #2E0410 !important;
        font-weight: bold !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(255,215,0,0.4) !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(255,215,0,0.2) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("<h1 style='color:#FFD700; text-align:center; margin-bottom:0px;'>🛕 Mandapam</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#FFE082; text-align:center; font-size:0.9rem; margin-top:0px;'>Sree Bhadra Samrakshana Seva Trust</p>", unsafe_allow_html=True)
        st.markdown("<hr style='margin:12px 0; border-color:rgba(255,215,0,0.3);'>", unsafe_allow_html=True)

        pages = {
            "Dashboard": "📊",
            "Hall Booking": "📅",
            "Payments": "💳",
            "Invoices": "🧾",
            "Expenses": "💸",
            "Thirumana Bond": "💍",
            "Assets": "🪑",
            "Reports": "📈",
            "Settings": "⚙️"
        }

        for page, icon in pages.items():
            if page == "Settings" and st.session_state.user.get("role") != "Admin":
                continue
            btn_type = "primary" if st.session_state.get("page") == page else "secondary"
            if st.button(f"{icon} {page}", use_container_width=True, type=btn_type):
                st.session_state.page = page
                st.rerun()

        st.markdown("<hr style='margin:16px 0; border-color:rgba(255,215,0,0.3);'>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True):
            do_logout()

        st.markdown(
            f"<p style='text-align:center; color:#FFE082; font-size:0.8rem; margin-top:10px;'>"
            f"👤 <b>{st.session_state.user.get('username','Admin')}</b><br>"
            f"<span style='color:#E8DCC4;'>{st.session_state.user.get('role','Admin')}</span></p>",
            unsafe_allow_html=True
        )

# ==================== DASHBOARD ====================
def dashboard_page():
    st.markdown("<h2 style='color:#8B1538;'>📊 Dashboard</h2>", unsafe_allow_html=True)

    try:
        bookings = supabase.table("bookings").select("*").execute().data or []
        payments = supabase.table("payments").select("*").execute().data or []
        invoices = supabase.table("invoices").select("*").execute().data or []
        expenses = supabase.table("expenses").select("*").execute().data or []
        assets = supabase.table("assets").select("*").execute().data or []
    except Exception as e:
        st.error(f"Data load error: {e}")
        return

    today = date.today().isoformat()
    this_month = today[:7]

    today_bookings = [b for b in bookings if b.get("event_date") == today]
    month_payments = [p for p in payments if str(p.get("payment_date", "")).startswith(this_month)]
    month_revenue = sum(p.get("amount", 0) for p in month_payments)
    total_invoices = len(invoices)
    total_assets = len(assets)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's Bookings", len(today_bookings))
    c2.metric("Monthly Revenue", fmt_currency(month_revenue))
    c3.metric("Invoices Generated", total_invoices)
    c4.metric("Total Assets", total_assets)

    st.markdown("<hr style='border-color:#E8DCC4; margin:20px 0;'>", unsafe_allow_html=True)

    st.markdown("### 📅 Upcoming Bookings (Next 7 Days)")
    upcoming = []
    for b in bookings:
        try:
            bdate = datetime.strptime(b["event_date"], "%Y-%m-%d").date()
            diff = (bdate - date.today()).days
            if 0 <= diff <= 7:
                upcoming.append(b)
        except Exception:
            pass
    upcoming.sort(key=lambda x: x["event_date"])
    if upcoming:
        df = pd.DataFrame(upcoming)[["event_date", "event_name", "customer_name", "phone", "hall_name", "status"]]
        df.columns = ["Date", "Event", "Customer", "Phone", "Hall", "Status"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No upcoming events in the next 7 days")

    st.markdown("### 📈 Monthly Revenue Trend (Last 6 Months)")
    months = []
    vals = []
    for i in range(5, -1, -1):
        d = datetime.now() - timedelta(days=i * 30)
        key = d.strftime("%Y-%m")
        months.append(d.strftime("%b"))
        m_payments = [p for p in payments if str(p.get("payment_date", "")).startswith(key)]
        vals.append(sum(p.get("amount", 0) for p in m_payments))

    chart_data = pd.DataFrame({"Month": months, "Revenue": vals})
    st.bar_chart(chart_data.set_index("Month"), use_container_width=True)

# ==================== BOOKING ====================
def booking_page():
    st.markdown("<h2 style='color:#8B1538;'>📅 Hall Booking</h2>", unsafe_allow_html=True)

    tab_list, tab_add = st.tabs(["📋 All Bookings", "➕ New Booking"])

    with tab_list:
        try:
            data = supabase.table("bookings").select("*").order("event_date", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Error: {e}")
            data = []

        if not data:
            st.info("No bookings found")
        else:
            enriched = []
            for b in data:
                bid = b["id"]
                pays = supabase.table("payments").select("amount").eq("booking_id", bid).execute().data or []
                total_paid = sum(p.get("amount", 0) for p in pays)
                enriched.append({**b, "paid": total_paid, "balance": b.get("total_amount", 0) - total_paid})

            df = pd.DataFrame(enriched)
            search = st.text_input("🔍 Search by name, phone or event", placeholder="Type to search...")
            if search:
                mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False))
                df = df[mask.any(axis=1)]

            display = df[["id", "event_date", "event_name", "customer_name", "phone", "hall_name", "total_amount", "paid", "balance", "status"]]
            display.columns = ["ID", "Date", "Event", "Customer", "Phone", "Hall", "Total", "Paid", "Balance", "Status"]
            st.dataframe(display, use_container_width=True, hide_index=True)

            st.markdown("---")
            del_opt = [""] + [f"{r['id']} - {r['event_name']}" for r in data]
            del_id = st.selectbox("Select Booking to Delete", del_opt)
            if del_id and st.button("Delete Selected", type="secondary"):
                bid = del_id.split(" - ")[0]
                try:
                    supabase.table("payments").delete().eq("booking_id", bid).execute()
                    supabase.table("invoices").delete().eq("booking_id", bid).execute()
                    supabase.table("bookings").delete().eq("id", bid).execute()
                    st.success("Deleted successfully")
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")

    with tab_add:
        with st.form("booking_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            event_name = c1.text_input("Event Name*", placeholder="e.g., Ram & Sita Wedding")
            customer = c2.text_input("Customer Name*")
            phone = c1.text_input("Phone Number*")
            email = c2.text_input("Email")
            bdate = c1.date_input("Event Date*", value=date.today())
            hall = c2.selectbox("Hall / Venue", ["Main Hall", "Mini Hall", "Open Lawn", "Dining Hall"])
            etype = c1.selectbox("Event Type", ["Wedding", "Reception", "Engagement", "Birthday", "Corporate", "Other"])
            amount = c2.number_input("Total Amount (₹)*", min_value=0, step=1000)
            address = st.text_area("Address")
            notes = st.text_area("Special Requirements")

            if st.form_submit_button("Save Booking", use_container_width=True, type="primary"):
                if not all([event_name, customer, phone, amount]):
                    st.error("Please fill all required fields (marked with *)")
                else:
                    try:
                        new_id = generate_id("B", "bookings")
                        row = {
                            "id": new_id, "event_name": event_name, "customer_name": customer,
                            "phone": phone, "email": email, "event_date": bdate.isoformat(),
                            "hall_name": hall, "event_type": etype, "total_amount": amount,
                            "address": address, "notes": notes, "status": "Confirmed"
                        }
                        supabase.table("bookings").insert(row).execute()
                        st.success(f"✅ Booking created: {new_id}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Save failed: {e}")

# ==================== PAYMENTS ====================
def payments_page():
    st.markdown("<h2 style='color:#8B1538;'>💳 Payment Tracking</h2>", unsafe_allow_html=True)
    st.caption("Record partial payments against a booking. Invoice can only be generated after full payment.")

    try:
        bookings = supabase.table("bookings").select("*").execute().data or []
    except Exception:
        st.error("Failed to load bookings")
        return

    if not bookings:
        st.info("No bookings available. Create a booking first.")
        return

    booking_opts = {f"{b['id']} - {b['event_name']} ({b['customer_name']})": b for b in bookings}
    selected = st.selectbox("Select Booking", list(booking_opts.keys()))
    booking = booking_opts[selected]
    bid = booking["id"]

    payments = supabase.table("payments").select("*").eq("booking_id", bid).order("payment_date", desc=True).execute().data or []
    total_paid = sum(p.get("amount", 0) for p in payments)
    balance = booking.get("total_amount", 0) - total_paid

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Amount", fmt_currency(booking.get("total_amount", 0)))
    c2.metric("Total Paid", fmt_currency(total_paid))
    delta_text = "Fully Paid" if balance <= 0 else f"Due: {fmt_currency(balance)}"
    c3.metric("Balance", fmt_currency(balance), delta=delta_text, delta_color="inverse")

    st.markdown("<hr style='border-color:#E8DCC4;'>", unsafe_allow_html=True)

    tab_history, tab_add = st.tabs(["📋 Payment History", "➕ Add Payment"])

    with tab_history:
        if payments:
            df = pd.DataFrame(payments)[["payment_date", "amount", "method", "notes"]]
            df.columns = ["Date", "Amount", "Method", "Notes"]
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("---")
            pay_del = st.selectbox("Remove Payment", [""] + [f"{p['id']} - ₹{p['amount']} on {p['payment_date']}" for p in payments])
            if pay_del and st.button("Delete Payment", type="secondary"):
                pid = pay_del.split(" - ")[0]
                try:
                    supabase.table("payments").delete().eq("id", pid).execute()
                    st.success("Payment deleted")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No payments recorded yet")

    with tab_add:
        if balance <= 0:
            st.success("✅ This booking is fully paid. Go to Invoices page to generate the invoice.")
        else:
            with st.form("payment_form", clear_on_submit=True):
                st.markdown(f"**Balance Remaining: {fmt_currency(balance)}**")
                pdate = st.date_input("Payment Date", value=date.today())
                pamount = st.number_input("Amount (₹)*", min_value=1, max_value=int(balance), step=100)
                pmethod = st.selectbox("Payment Method", ["Cash", "UPI / GPay", "Bank Transfer", "Cheque"])
                pnotes = st.text_area("Notes / Reference")
                if st.form_submit_button("Record Payment", type="primary"):
                    try:
                        row = {
                            "booking_id": bid, "amount": pamount,
                            "payment_date": pdate.isoformat(), "method": pmethod, "notes": pnotes
                        }
                        supabase.table("payments").insert(row).execute()
                        st.success("Payment recorded successfully")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

# ==================== INVOICES ====================
def invoices_page():
    st.markdown("<h2 style='color:#8B1538;'>🧾 Invoice Generation</h2>", unsafe_allow_html=True)
    st.caption("Invoices are generated ONLY after full payment is received for a booking.")

    tab_gen, tab_view = st.tabs(["➕ Generate Invoice", "📋 View Invoices"])

    with tab_gen:
        try:
            bookings = supabase.table("bookings").select("*").execute().data or []
        except Exception:
            st.error("Failed to load bookings")
            return

        eligible = []
        for b in bookings:
            bid = b["id"]
            pays = supabase.table("payments").select("amount").eq("booking_id", bid).execute().data or []
            total_paid = sum(p.get("amount", 0) for p in pays)
            existing = supabase.table("invoices").select("id").eq("booking_id", bid).execute().data
            if total_paid >= b.get("total_amount", 0) and not existing:
                eligible.append(b)

        if not eligible:
            st.info("No eligible bookings. Ensure a booking is fully paid and not already invoiced.")
        else:
            opts = {f"{b['id']} - {b['event_name']} ({b['customer_name']})": b for b in eligible}
            selected = st.selectbox("Select Fully-Paid Booking", list(opts.keys()))
            booking = opts[selected]
            bid = booking["id"]

            pays = supabase.table("payments").select("*").eq("booking_id", bid).execute().data or []
            total_paid = sum(p.get("amount", 0) for p in pays)

            st.markdown(f"""
            <div style="background:#FFFBF5; padding:16px; border-radius:10px; border-left:5px solid #2E7D32; margin-bottom:12px;">
                <b>Booking ID:</b> {bid}<br>
                <b>Customer:</b> {booking.get('customer_name','-')}<br>
                <b>Event:</b> {booking.get('event_name','-')}<br>
                <b>Total Amount:</b> {fmt_currency(booking.get('total_amount',0))}<br>
                <b>Total Paid:</b> {fmt_currency(total_paid)}<br>
                <b>Status:</b> ✅ Ready for Invoice
            </div>
            """, unsafe_allow_html=True)

            inv_date = st.date_input("Invoice Date", value=date.today())
            inv_notes = st.text_area("Invoice Notes / Terms")

            if st.button("Generate Invoice", type="primary", use_container_width=True):
                try:
                    inv_id = generate_id("INV", "invoices")
                    methods = ", ".join(list(set(p.get("method", "") for p in pays)))
                    row = {
                        "id": inv_id, "booking_id": bid, "invoice_date": inv_date.isoformat(),
                        "total_amount": booking.get("total_amount", 0), "total_paid": total_paid,
                        "payment_method_summary": methods, "status": "Paid", "notes": inv_notes
                    }
                    supabase.table("invoices").insert(row).execute()
                    st.success(f"🎉 Invoice {inv_id} generated successfully!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Invoice generation failed: {e}")

    with tab_view:
        try:
            invoices = supabase.table("invoices").select("*, bookings(*)").order("invoice_date", desc=True).execute().data or []
        except Exception:
            st.error("Failed to load invoices")
            return

        if not invoices:
            st.info("No invoices generated yet")
            return

        is_admin = st.session_state.user.get("role") == "Admin"

        for inv in invoices:
            bk = inv.get("bookings", {})
            with st.container():
                st.markdown(f"""
                <div style="border:2px solid #8B1538; border-radius:14px; padding:18px; margin-bottom:14px; background:#FFFBF5;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h3 style="color:#8B1538; margin:0; font-size:1.2rem;">🧾 Invoice {inv['id']}</h3>
                        <span style="background:#2E7D32; color:white; padding:4px 14px; border-radius:20px; font-size:0.8rem; font-weight:600;">{inv.get('status','Paid')}</span>
                    </div>
                    <hr style="border-color:#E8DCC4; margin:10px 0;">
                    <p style="margin:4px 0;"><b>Date:</b> {fmt_date(inv.get('invoice_date'))} &nbsp;|&nbsp; <b>Booking:</b> {inv['booking_id']}</p>
                    <p style="margin:4px 0;"><b>Customer:</b> {bk.get('customer_name','-')} &nbsp;|&nbsp; <b>Phone:</b> {bk.get('phone','-')}</p>
                    <p style="margin:4px 0;"><b>Event:</b> {bk.get('event_name','-')} &nbsp;|&nbsp; <b>Hall:</b> {bk.get('hall_name','-')}</p>
                    <div style="display:flex; gap:28px; margin-top:12px; flex-wrap:wrap;">
                        <div><b>Total:</b> {fmt_currency(inv.get('total_amount',0))}</div>
                        <div><b>Paid:</b> {fmt_currency(inv.get('total_paid',0))}</div>
                        <div><b>Methods:</b> {inv.get('payment_method_summary','-')}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Action buttons
                c1, c2, c3, c4 = st.columns([1, 1, 1, 2])

                # PDF Download
                with c1:
                    pays = supabase.table("payments").select("*").eq("booking_id", inv["booking_id"]).execute().data or []
                    pdf_buffer = generate_invoice_pdf(inv, bk, pays)
                    st.download_button(
                        label="📄 PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=f"Invoice_{inv['id']}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{inv['id']}"
                    )

                # WhatsApp
                with c2:
                    if bk.get("phone"):
                        wa_link = get_whatsapp_link(bk["phone"], inv["id"], inv.get("total_amount", 0))
                        st.markdown(f'<a href="{wa_link}" target="_blank"><button style="width:100%; padding:6px; border-radius:6px; background:#25D366; color:white; border:none; font-weight:600; cursor:pointer;">📱 WhatsApp</button></a>', unsafe_allow_html=True)
                    else:
                        st.button("📱 WhatsApp", disabled=True, key=f"wa_disabled_{inv['id']}")

                # Edit (Admin only)
                with c3:
                    if is_admin:
                        if st.button("✏️ Edit", key=f"edit_{inv['id']}"):
                            st.session_state[f"edit_inv_{inv['id']}"] = True
                    else:
                        st.button("✏️ Edit", disabled=True, key=f"edit_dis_{inv['id']}")

                # Delete (Admin only)
                with c4:
                    if is_admin:
                        if st.button("🗑️ Delete Invoice", key=f"del_{inv['id']}"):
                            try:
                                supabase.table("invoices").delete().eq("id", inv["id"]).execute()
                                st.success("Invoice deleted")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                    else:
                        st.button("🗑️ Delete Invoice", disabled=True, key=f"del_dis_{inv['id']}")

                # Edit form
                if is_admin and st.session_state.get(f"edit_inv_{inv['id']}", False):
                    with st.form(f"edit_form_{inv['id']}"):
                        st.markdown(f"**Edit Invoice {inv['id']}**")
                        new_date = st.date_input("Invoice Date", value=datetime.strptime(inv.get("invoice_date", date.today().isoformat()), "%Y-%m-%d").date(), key=f"ed_dt_{inv['id']}")
                        new_status = st.selectbox("Status", ["Paid", "Cancelled"], index=0 if inv.get("status")=="Paid" else 1, key=f"ed_st_{inv['id']}")
                        new_notes = st.text_area("Notes", value=inv.get("notes", ""), key=f"ed_nt_{inv['id']}")
                        if st.form_submit_button("Save Changes", type="primary"):
                            try:
                                supabase.table("invoices").update({
                                    "invoice_date": new_date.isoformat(),
                                    "status": new_status,
                                    "notes": new_notes
                                }).eq("id", inv["id"]).execute()
                                st.success("Invoice updated")
                                del st.session_state[f"edit_inv_{inv['id']}"]
                                st.rerun()
                            except Exception as e:
                                st.error(f"Update failed: {e}")

                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ==================== EXPENSES ====================
def expenses_page():
    st.markdown("<h2 style='color:#8B1538;'>💸 Expense Management</h2>", unsafe_allow_html=True)
    cats = get_expense_categories()

    tab_list, tab_add = st.tabs(["📋 All Expenses", "➕ Add Expense"])

    with tab_list:
        try:
            data = supabase.table("expenses").select("*").order("expense_date", desc=True).execute().data or []
        except Exception as e:
            st.error(f"Error: {e}")
            data = []

        if data:
            df = pd.DataFrame(data)
            c1, c2 = st.columns([3, 1])
            search = c1.text_input("🔍 Search expenses")
            cat = c2.selectbox("Category", ["All"] + cats)

            if search:
                mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False))
                df = df[mask.any(axis=1)]
            if cat != "All":
                df = df[df["category"] == cat]

            display = df[["expense_date", "category", "description", "amount", "paid_to"]]
            display.columns = ["Date", "Category", "Description", "Amount", "Vendor"]
            st.dataframe(display, use_container_width=True, hide_index=True)

            total = df["amount"].sum() if not df.empty else 0
            st.markdown(f"**Total Filtered Amount:** {fmt_currency(total)}")

            st.markdown("---")
            del_opt = [""] + [f"{r['id']} - {r['description'][:30]}" for r in data]
            del_id = st.selectbox("Delete Expense", del_opt)
            if del_id and st.button("Delete", type="secondary"):
                eid = del_id.split(" - ")[0]
                try:
                    supabase.table("expenses").delete().eq("id", eid).execute()
                    st.success("Deleted")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No expenses recorded")

    with tab_add:
        with st.form("expense_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            edate = c1.date_input("Date", value=date.today())
            ecat = c2.selectbox("Category", cats)
            eamt = c1.number_input("Amount (₹)*", min_value=0, step=100)
            epaid = c2.text_input("Paid To / Vendor*")
            edesc = st.text_area("Description*")

            if st.form_submit_button("Save Expense", type="primary"):
                if not all([eamt, epaid, edesc]):
                    st.error("Fill required fields")
                else:
                    try:
                        eid = generate_id("E", "expenses")
                        supabase.table("expenses").insert({
                            "id": eid, "expense_date": edate.isoformat(), "category": ecat,
                            "amount": eamt, "paid_to": epaid, "description": edesc
                        }).execute()
                        st.success("Expense saved")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

# ==================== BONDS ====================
def bonds_page():
    st.markdown("<h2 style='color:#8B1538;'>💍 Thirumana Bond</h2>", unsafe_allow_html=True)

    tab_list, tab_add = st.tabs(["📋 All Bonds", "➕ New Bond"])

    with tab_list:
        try:
            data = supabase.table("bonds").select("*").order("bond_date", desc=True).execute().data or []
        except Exception:
            st.error("Failed to load bonds")
            return

        if data:
            df = pd.DataFrame(data)[["id", "groom_name", "bride_name", "address", "bond_date", "phone", "photo_url", "document_url"]]
            df.columns = ["Bond ID", "Groom", "Bride", "Address", "Bond Date", "Phone", "Photo", "Document"]
            df["Photo"] = df["Photo"].apply(lambda x: "✅ Uploaded" if x else "❌ None")
            df["Document"] = df["Document"].apply(lambda x: "✅ Uploaded" if x else "❌ None")
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("---")
            view_opt = [""] + [f"{r['id']} - {r['groom_name']} & {r['bride_name']}" for r in data]
            view_id = st.selectbox("View Bond Details", view_opt)
            if view_id:
                bid = view_id.split(" - ")[0]
                b = next((x for x in data if x["id"] == bid), None)
                if b:
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.markdown(f"""
                        **Groom:** {b.get('groom_name','-')}  
                        **Bride:** {b.get('bride_name','-')}  
                        **Address:** {b.get('address','-')}  
                        **Bond Date:** {fmt_date(b.get('bond_date'))}  
                        **Phone:** {b.get('phone','-')}  
                        """)
                    with c2:
                        if b.get("photo_url"):
                            st.image(b["photo_url"], caption="Couple Photo", width=200)
                        if b.get("document_url"):
                            st.markdown(f"[📄 View Document]({b['document_url']})")

            del_opt = [""] + [f"{r['id']} - {r['groom_name']} & {r['bride_name']}" for r in data]
            del_id = st.selectbox("Delete Bond", del_opt)
            if del_id and st.button("Delete Bond", type="secondary"):
                bid = del_id.split(" - ")[0]
                try:
                    supabase.table("bonds").delete().eq("id", bid).execute()
                    st.success("Deleted")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No bonds registered")

    with tab_add:
        with st.form("bond_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            groom = c1.text_input("Groom's Name*")
            bride = c2.text_input("Bride's Name*")
            addr = st.text_area("Address*")
            bdate = st.date_input("Bond Issued Date*", value=date.today())
            phone = st.text_input("Contact Phone")

            photo = st.file_uploader("Upload Couple Photo", type=["jpg", "jpeg", "png"])
            doc = st.file_uploader("Upload Bond Document", type=["jpg", "jpeg", "png", "pdf"])

            if st.form_submit_button("Save Bond", type="primary"):
                if not all([groom, bride, addr, bdate]):
                    st.error("Fill required fields")
                else:
                    try:
                        bid = generate_id("TB", "bonds")
                        photo_url = None
                        doc_url = None

                        if photo:
                            path = f"bonds/{bid}_photo.{photo.name.split('.')[-1]}"
                            supabase.storage.from_("documents").upload(path, photo.getvalue())
                            photo_url = supabase.storage.from_("documents").get_public_url(path)

                        if doc:
                            path = f"bonds/{bid}_doc.{doc.name.split('.')[-1]}"
                            supabase.storage.from_("documents").upload(path, doc.getvalue())
                            doc_url = supabase.storage.from_("documents").get_public_url(path)

                        supabase.table("bonds").insert({
                            "id": bid, "groom_name": groom, "bride_name": bride, "address": addr,
                            "bond_date": bdate.isoformat(), "phone": phone,
                            "photo_url": photo_url, "document_url": doc_url
                        }).execute()
                        st.success(f"Bond {bid} saved successfully")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Save failed: {e}")

# ==================== ASSETS ====================
def assets_page():
    st.markdown("<h2 style='color:#8B1538;'>🪑 Asset Management</h2>", unsafe_allow_html=True)

    tab_list, tab_add = st.tabs(["📋 All Assets", "➕ Add Asset"])

    with tab_list:
        try:
            data = supabase.table("assets").select("*").execute().data or []
        except Exception:
            st.error("Failed to load assets")
            return

        if data:
            df = pd.DataFrame(data)
            c1, c2 = st.columns([3, 1])
            search = c1.text_input("🔍 Search assets")
            status = c2.selectbox("Status", ["All", "Good", "Needs Repair", "Damaged"])

            if search:
                mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False))
                df = df[mask.any(axis=1)]
            if status != "All":
                df = df[df["current_status"] == status]

            display = df[["id", "asset_name", "category", "purchase_date", "purchase_value", "current_status", "last_service_date"]]
            display.columns = ["ID", "Name", "Category", "Purchase Date", "Value", "Status", "Last Service"]
            st.dataframe(display, use_container_width=True, hide_index=True)

            total_val = df["purchase_value"].sum() if not df.empty else 0
            repair_count = len([a for a in data if a.get("current_status") == "Needs Repair"])

            c1, c2 = st.columns(2)
            c1.metric("Total Asset Value", fmt_currency(total_val))
            c2.metric("Need Maintenance", repair_count)

            # Barcode viewer
            st.markdown("---")
            st.markdown("### 🏷️ Asset Barcode")
            bc_opt = [""] + [f"{r['id']} - {r['asset_name']}" for r in data]
            bc_sel = st.selectbox("Select Asset for Barcode", bc_opt)
            if bc_sel:
                aid = bc_sel.split(" - ")[0]
                a = next((x for x in data if x["id"] == aid), None)
                if a:
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        buf = generate_barcode(aid)
                        st.image(buf, caption=f"Barcode: {aid}")
                    with c2:
                        st.markdown(f"**Asset:** {a.get('asset_name')}")
                        st.markdown(f"**Category:** {a.get('category')}")
                        st.markdown(f"**Status:** {a.get('current_status')}")
                        st.download_button(
                            label="📥 Download Barcode PNG",
                            data=buf.getvalue(),
                            file_name=f"barcode_{aid}.png",
                            mime="image/png",
                            key=f"dl_bc_{aid}"
                        )

            st.markdown("---")
            del_opt = [""] + [f"{r['id']} - {r['asset_name']}" for r in data]
            del_id = st.selectbox("Delete Asset", del_opt)
            if del_id and st.button("Delete", type="secondary"):
                aid = del_id.split(" - ")[0]
                try:
                    supabase.table("assets").delete().eq("id", aid).execute()
                    st.success("Deleted")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No assets found")

    with tab_add:
        with st.form("asset_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Asset Name*")
            cat = c2.selectbox("Category", ["Furniture", "Electronics", "Kitchen", "Decoration", "Sound System", "Lighting", "Other"])
            pdate = c1.date_input("Purchase Date*", value=date.today())
            val = c2.number_input("Purchase Value (₹)*", min_value=0, step=500)
            stat = c1.selectbox("Current Status", ["Good", "Needs Repair", "Damaged"])
            svc = c2.date_input("Last Service Date", value=date.today())
            notes = st.text_area("Notes / Maintenance History")

            if st.form_submit_button("Save Asset", type="primary"):
                if not all([name, pdate, val]):
                    st.error("Fill required fields")
                else:
                    try:
                        aid = generate_id("A", "assets")
                        supabase.table("assets").insert({
                            "id": aid, "asset_name": name, "category": cat, "purchase_date": pdate.isoformat(),
                            "purchase_value": val, "current_status": stat, "last_service_date": svc.isoformat(),
                            "notes": notes
                        }).execute()
                        st.success("Asset saved")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

# ==================== REPORTS ====================
def reports_page():
    st.markdown("<h2 style='color:#8B1538;'>📈 Reports</h2>", unsafe_allow_html=True)

    rtype = st.selectbox("Report Type", ["Booking Report", "Revenue Report", "Expense Report"])
    c1, c2 = st.columns(2)
    dfrom = c1.date_input("From Date", value=date.today().replace(day=1))
    dto = c2.date_input("To Date", value=date.today())

    if st.button("Generate Report", type="primary"):
        fstr = dfrom.isoformat()
        tstr = dto.isoformat()

        report_df = pd.DataFrame()
        report_title = ""

        if rtype == "Booking Report":
            try:
                data = supabase.table("bookings").select("*").gte("event_date", fstr).lte("event_date", tstr).execute().data or []
            except Exception as e:
                st.error(f"Error: {e}")
                data = []
            report_title = f"Booking Report ({fmt_date(fstr)} to {fmt_date(tstr)})"
            if data:
                report_df = pd.DataFrame(data)[["event_date", "event_name", "customer_name", "hall_name", "event_type", "total_amount", "status"]]
                report_df.columns = ["Date", "Event", "Customer", "Hall", "Type", "Amount", "Status"]
                st.dataframe(report_df, use_container_width=True, hide_index=True)
                st.markdown(f"**Total Bookings:** {len(data)} | **Total Value:** {fmt_currency(sum(b.get('total_amount', 0) for b in data))}")
            else:
                st.info("No bookings in selected range")

        elif rtype == "Revenue Report":
            try:
                data = supabase.table("payments").select("*, bookings(event_name, customer_name)").gte("payment_date", fstr).lte("payment_date", tstr).execute().data or []
            except Exception as e:
                st.error(f"Error: {e}")
                data = []
            report_title = f"Revenue Report ({fmt_date(fstr)} to {fmt_date(tstr)})"
            if data:
                for d in data:
                    bk = d.get("bookings", {})
                    d["event_name"] = bk.get("event_name", "")
                    d["customer_name"] = bk.get("customer_name", "")
                report_df = pd.DataFrame(data)[["payment_date", "customer_name", "event_name", "amount", "method"]]
                report_df.columns = ["Date", "Customer", "Event", "Amount", "Method"]
                st.dataframe(report_df, use_container_width=True, hide_index=True)
                st.markdown(f"**Total Revenue:** {fmt_currency(report_df['Amount'].sum())}")
            else:
                st.info("No payments in selected range")

        elif rtype == "Expense Report":
            try:
                data = supabase.table("expenses").select("*").gte("expense_date", fstr).lte("expense_date", tstr).execute().data or []
            except Exception as e:
                st.error(f"Error: {e}")
                data = []
            report_title = f"Expense Report ({fmt_date(fstr)} to {fmt_date(tstr)})"
            if data:
                report_df = pd.DataFrame(data)[["expense_date", "category", "description", "amount", "paid_to"]]
                report_df.columns = ["Date", "Category", "Description", "Amount", "Vendor"]
                st.dataframe(report_df, use_container_width=True, hide_index=True)
                st.markdown(f"**Total Expenses:** {fmt_currency(report_df['Amount'].sum())}")
            else:
                st.info("No expenses in selected range")

        # Download buttons
        if not report_df.empty:
            st.markdown("---")
            st.markdown("### 📥 Download Report")
            dc1, dc2, dc3 = st.columns(3)

            with dc1:
                csv = report_df.to_csv(index=False).encode('utf-8')
                st.download_button("📄 CSV", csv, f"{report_title.replace(' ', '_')}.csv", "text/csv")

            with dc2:
                excel_buffer = io.BytesIO()
                report_df.to_excel(excel_buffer, index=False, engine='openpyxl')
                st.download_button("📊 Excel", excel_buffer.getvalue(), f"{report_title.replace(' ', '_')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            with dc3:
                pdf_buffer = generate_report_pdf(report_title, report_df)
                st.download_button("📕 PDF", pdf_buffer.getvalue(), f"{report_title.replace(' ', '_')}.pdf", "application/pdf")

# ==================== SETTINGS ====================
def settings_page():
    st.markdown("<h2 style='color:#8B1538;'>⚙️ Settings</h2>", unsafe_allow_html=True)

    if st.session_state.user.get("role") != "Admin":
        st.error("🚫 Admin access only")
        return

    tab_users, tab_cats, tab_config = st.tabs(["👤 User Management", "📂 Expense Categories", "🎨 App Config"])

    with tab_users:
        st.markdown("#### Manage Users")
        try:
            users = supabase.table("users").select("*").order("username").execute().data or []
        except Exception:
            st.error("Failed to load users")
            users = []

        if users:
            df = pd.DataFrame(users)[["username", "role", "created_at"]]
            df.columns = ["Username", "Role", "Created"]
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("**Add New User**")
        with st.form("user_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            new_user = c1.text_input("Username*")
            new_pass = c2.text_input("Password*", type="password")
            new_role = st.selectbox("Role", ["Admin", "Manager", "Staff"])
            if st.form_submit_button("Add User", type="primary"):
                if not new_user or not new_pass:
                    st.error("Fill required fields")
                else:
                    try:
                        supabase.table("users").insert({
                            "username": new_user, "password_hash": new_pass, "role": new_role
                        }).execute()
                        st.success(f"User {new_user} added")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

        if users:
            st.markdown("---")
            del_opt = [""] + [f"{u['id']} - {u['username']} ({u['role']})" for u in users if u['username'] != st.session_state.user.get('username')]
            del_user = st.selectbox("Delete User (Cannot delete yourself)", del_opt)
            if del_user and st.button("Delete User", type="secondary"):
                uid = del_user.split(" - ")[0]
                try:
                    supabase.table("users").delete().eq("id", uid).execute()
                    st.success("User deleted")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab_cats:
        st.markdown("#### Expense Categories")
        cats = get_expense_categories()
        st.write("Current categories:", ", ".join([f"`{c}`" for c in cats]))

        st.markdown("---")
        with st.form("cat_form", clear_on_submit=True):
            new_cat = st.text_input("New Category Name*")
            if st.form_submit_button("Add Category", type="primary"):
                if not new_cat:
                    st.error("Enter a name")
                else:
                    try:
                        supabase.table("expense_categories").insert({"name": new_cat}).execute()
                        st.success("Category added")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed (may already exist): {e}")

        st.markdown("---")
        del_cat = st.selectbox("Remove Category", [""] + cats)
        if del_cat and st.button("Remove Category", type="secondary"):
            try:
                supabase.table("expense_categories").delete().eq("name", del_cat).execute()
                st.success("Category removed")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    with tab_config:
        st.markdown("#### App Configuration")
        st.markdown("Upload the Goddess Bhadreshwariamman image for the login page.")

        current_url = get_setting("login_image_url")
        if current_url:
            st.image(current_url, caption="Current Login Image", width=200)

        uploaded = st.file_uploader("Upload New Login Image", type=["jpg", "jpeg", "png"])
        if uploaded and st.button("Save Login Image", type="primary"):
            try:
                path = f"config/login_image.{uploaded.name.split('.')[-1]}"
                supabase.storage.from_("documents").upload(path, uploaded.getvalue(), {"upsert": "true"})
                url = supabase.storage.from_("documents").get_public_url(path)
                set_setting("login_image_url", url)
                st.success("Login image updated!")
                st.rerun()
            except Exception as e:
                st.error(f"Upload failed: {e}")

        st.markdown("---")
        st.markdown("**Remove Login Image**")
        if current_url and st.button("Remove Image", type="secondary"):
            set_setting("login_image_url", "")
            st.success("Image removed. Default icon will show.")
            st.rerun()

# ==================== MAIN ====================
def main():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"

    if not st.session_state.authenticated:
        login_page()
    else:
        sidebar_nav()
        page = st.session_state.page

        if page == "Dashboard":
            dashboard_page()
        elif page == "Hall Booking":
            booking_page()
        elif page == "Payments":
            payments_page()
        elif page == "Invoices":
            invoices_page()
        elif page == "Expenses":
            expenses_page()
        elif page == "Thirumana Bond":
            bonds_page()
        elif page == "Assets":
            assets_page()
        elif page == "Reports":
            reports_page()
        elif page == "Settings":
            settings_page()

if __name__ == "__main__":
    main()
