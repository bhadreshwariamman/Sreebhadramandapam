import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, date, timedelta
import uuid

st.set_page_config(
    page_title="Thirumana Mandapam Management",
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

# ==================== AUTH ====================
def login_page():
    st.markdown("""
    <style>
    .login-box {
        max-width: 420px; margin: auto; margin-top: 80px; padding: 40px;
        border-radius: 16px; background: #FFFBF5; border: 2px solid #8B1538;
        box-shadow: 0 4px 16px rgba(139,21,56,0.15);
    }
    .login-title { color: #8B1538; text-align: center; margin-bottom: 8px; }
    .login-sub { color: #B8860B; text-align: center; margin-bottom: 24px; font-size: 0.95rem; }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("<h1 class='login-title'>🛕 Thirumana Mandapam</h1>", unsafe_allow_html=True)
        st.markdown("<p class='login-sub'>Management System</p>", unsafe_allow_html=True)

        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password", value="admin")

        if st.button("Sign In", use_container_width=True, type="primary"):
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
        st.markdown("<p style='text-align:center;color:#999;font-size:0.8rem;margin-top:12px;'>Default: admin / admin</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ==================== HELPERS ====================
def generate_id(prefix: str, table: str) -> str:
    """Generate next sequential ID like B001, INV001."""
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

# ==================== SIDEBAR ====================
def sidebar_nav():
    with st.sidebar:
        st.markdown("## 🛕 Mandapam")
        st.markdown("<p style='color:#B8860B;font-size:0.9rem;'>Management System</p>", unsafe_allow_html=True)
        st.markdown("---")

        pages = {
            "Dashboard": "📊",
            "Hall Booking": "📅",
            "Payments": "💳",
            "Invoices": "🧾",
            "Expenses": "💸",
            "Thirumana Bond": "💍",
            "Assets": "🪑",
            "Reports": "📈"
        }

        for page, icon in pages.items():
            btn_type = "primary" if st.session_state.get("page") == page else "secondary"
            if st.button(f"{icon} {page}", use_container_width=True, type=btn_type):
                st.session_state.page = page
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

        st.markdown(
            f"<small>👤 <b>{st.session_state.user.get('username','Admin')}</b></small>",
            unsafe_allow_html=True
        )

# ==================== DASHBOARD ====================
def dashboard_page():
    st.markdown("## 📊 Dashboard")

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

    st.markdown("---")

    # Upcoming events
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

    # Revenue chart
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
    st.markdown("## 📅 Hall Booking")

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
            # Compute paid/balance per booking
            enriched = []
            for b in data:
                bid = b["id"]
                pays = supabase.table("payments").select("amount").eq("booking_id", bid).execute().data or []
                total_paid = sum(p.get("amount", 0) for p in pays)
                enriched.append({
                    **b,
                    "paid": total_paid,
                    "balance": b.get("total_amount", 0) - total_paid
                })

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

            submitted = st.form_submit_button("Save Booking", use_container_width=True, type="primary")
            if submitted:
                if not all([event_name, customer, phone, amount]):
                    st.error("Please fill all required fields (marked with *)")
                else:
                    try:
                        new_id = generate_id("B", "bookings")
                        row = {
                            "id": new_id,
                            "event_name": event_name,
                            "customer_name": customer,
                            "phone": phone,
                            "email": email,
                            "event_date": bdate.isoformat(),
                            "hall_name": hall,
                            "event_type": etype,
                            "total_amount": amount,
                            "address": address,
                            "notes": notes,
                            "status": "Confirmed"
                        }
                        supabase.table("bookings").insert(row).execute()
                        st.success(f"✅ Booking created: {new_id}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Save failed: {e}")

# ==================== PAYMENTS ====================
def payments_page():
    st.markdown("## 💳 Payment Tracking")
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

    # Load payments
    payments = supabase.table("payments").select("*").eq("booking_id", bid).order("payment_date", desc=True).execute().data or []
    total_paid = sum(p.get("amount", 0) for p in payments)
    balance = booking.get("total_amount", 0) - total_paid

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Amount", fmt_currency(booking.get("total_amount", 0)))
    c2.metric("Total Paid", fmt_currency(total_paid))
    delta_text = "Fully Paid" if balance <= 0 else f"Due: {fmt_currency(balance)}"
    c3.metric("Balance", fmt_currency(balance), delta=delta_text, delta_color="inverse")

    st.markdown("---")

    tab_history, tab_add = st.tabs(["📋 Payment History", "➕ Add Payment"])

    with tab_history:
        if payments:
            df = pd.DataFrame(payments)[["payment_date", "amount", "method", "notes"]]
            df.columns = ["Date", "Amount", "Method", "Notes"]
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Allow delete payment
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
                            "booking_id": bid,
                            "amount": pamount,
                            "payment_date": pdate.isoformat(),
                            "method": pmethod,
                            "notes": pnotes
                        }
                        supabase.table("payments").insert(row).execute()
                        st.success("Payment recorded successfully")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

# ==================== INVOICES ====================
def invoices_page():
    st.markdown("## 🧾 Invoice Generation")
    st.caption("Invoices are generated ONLY after full payment is received for a booking.")

    tab_gen, tab_view = st.tabs(["➕ Generate Invoice", "📋 View Invoices"])

    with tab_gen:
        try:
            bookings = supabase.table("bookings").select("*").execute().data or []
        except Exception:
            st.error("Failed to load bookings")
            return

        # Filter: fully paid and not yet invoiced
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
            <div style="background:#FFFBF5; padding:16px; border-radius:8px; border-left:4px solid #2E7D32; margin-bottom:12px;">
                <b>Booking ID:</b> {bid}<br>
                <b>Customer:</b> {booking.get('customer_name','-')}<br>
                <b>Event:</b> {booking.get('event_name','-')}<br>
                <b>Total Amount:</b> {fmt_currency(booking.get('total_amount',0))}<br>
                <b>Total Paid:</b> {fmt_currency(total_paid)}<br>
                <b>Status:</b> ✅ Ready for Invoice
            </div>
            """, unsafe_allow_html=True)

            inv_date = st.date_input("Invoice Date", value=date.today())

            if st.button("Generate Invoice", type="primary", use_container_width=True):
                try:
                    inv_id = generate_id("INV", "invoices")
                    methods = ", ".join(list(set(p.get("method", "") for p in pays)))
                    row = {
                        "id": inv_id,
                        "booking_id": bid,
                        "invoice_date": inv_date.isoformat(),
                        "total_amount": booking.get("total_amount", 0),
                        "total_paid": total_paid,
                        "payment_method_summary": methods,
                        "status": "Paid"
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

        for inv in invoices:
            bk = inv.get("bookings", {})
            with st.container():
                st.markdown(f"""
                <div style="border:2px solid #8B1538; border-radius:12px; padding:16px; margin-bottom:12px; background:#FFFBF5;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h3 style="color:#8B1538; margin:0;">🧾 Invoice {inv['id']}</h3>
                        <span style="background:#2E7D32; color:white; padding:4px 12px; border-radius:12px; font-size:0.8rem;">{inv.get('status','Paid')}</span>
                    </div>
                    <hr style="border-color:#E8DCC4;">
                    <p><b>Date:</b> {fmt_date(inv.get('invoice_date'))} &nbsp;|&nbsp; <b>Booking:</b> {inv['booking_id']}</p>
                    <p><b>Customer:</b> {bk.get('customer_name','-')} &nbsp;|&nbsp; <b>Phone:</b> {bk.get('phone','-')}</p>
                    <p><b>Event:</b> {bk.get('event_name','-')} &nbsp;|&nbsp; <b>Hall:</b> {bk.get('hall_name','-')}</p>
                    <div style="display:flex; gap:24px; margin-top:12px;">
                        <div><b>Total:</b> {fmt_currency(inv.get('total_amount',0))}</div>
                        <div><b>Paid:</b> {fmt_currency(inv.get('total_paid',0))}</div>
                        <div><b>Methods:</b> {inv.get('payment_method_summary','-')}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button(f"🖨️ Print", key=f"print_{inv['id']}"):
                        print_invoice_html(inv, bk)

@st.dialog("Print Invoice")
def print_invoice_html(inv, bk):
    html = f"""
    <html>
    <head><title>Invoice {inv['id']}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial; max-width: 700px; margin: 40px auto; padding: 30px;
               border: 3px solid #8B1538; background: #FFFBF5; }}
        h1 {{ color: #8B1538; text-align: center; margin-bottom: 0; font-size: 2rem; }}
        h2 {{ text-align: center; color: #B8860B; margin-top: 0; font-size: 1.3rem; }}
        .row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #E8DCC4; }}
        .label {{ font-weight: bold; color: #8B1538; min-width: 160px; }}
        .total {{ font-size: 1.3rem; font-weight: bold; color: #8B1538; margin-top: 10px;
                  border-top: 2px solid #8B1538; padding-top: 10px; }}
        .footer {{ text-align: center; margin-top: 40px; color: #666; font-size: 0.9rem; }}
        .stamp {{ text-align: center; margin-top: 30px; color: #2E7D32; font-size: 1.2rem; font-weight: bold;
                  border: 2px dashed #2E7D32; padding: 8px; display: inline-block; }}
    </style></head>
    <body>
        <h1>🛕 THIRUMANA MANDAPAM</h1>
        <h2>TAX INVOICE</h2>
        <div class="row"><span class="label">Invoice #:</span><span>{inv['id']}</span></div>
        <div class="row"><span class="label">Date:</span><span>{fmt_date(inv.get('invoice_date'))}</span></div>
        <div class="row"><span class="label">Booking Ref:</span><span>{inv['booking_id']}</span></div>
        <div class="row"><span class="label">Customer:</span><span>{bk.get('customer_name','-')}</span></div>
        <div class="row"><span class="label">Phone:</span><span>{bk.get('phone','-')}</span></div>
        <div class="row"><span class="label">Event:</span><span>{bk.get('event_name','-')}</span></div>
        <div class="row"><span class="label">Hall:</span><span>{bk.get('hall_name','-')}</span></div>
        <div class="row"><span class="label">Address:</span><span>{bk.get('address','-')}</span></div>
        <div class="row total"><span>Total Amount:</span><span>{fmt_currency(inv.get('total_amount',0))}</span></div>
        <div class="row total"><span>Amount Paid:</span><span>{fmt_currency(inv.get('total_paid',0))}</span></div>
        <div class="row total"><span>Payment Methods:</span><span>{inv.get('payment_method_summary','-')}</span></div>
        <div style="text-align:center; margin-top:20px;">
            <div class="stamp">✅ PAID IN FULL</div>
        </div>
        <div class="footer">
            Thank you for choosing our mandapam!<br>
            Contact: 9876543210 | Email: mandapam@example.com
        </div>
    </body></html>
    """
    st.download_button(
        label="📄 Download Invoice HTML (Open in Browser to Print)",
        data=html,
        file_name=f"Invoice_{inv['id']}.html",
        mime="text/html"
    )
    st.info("Download the file, open it in your browser, and press Ctrl+P to print.")

# ==================== EXPENSES ====================
def expenses_page():
    st.markdown("## 💸 Expense Management")

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
            cat = c2.selectbox("Category", ["All", "Maintenance", "Staff", "Utilities", "Decoration", "Other"])

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

            # Delete
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
            ecat = c2.selectbox("Category", ["Maintenance", "Staff", "Utilities", "Decoration", "Other"])
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
    st.markdown("## 💍 Thirumana Bond")

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
            # Replace URLs with indicators
            df["Photo"] = df["Photo"].apply(lambda x: "✅ Uploaded" if x else "❌ None")
            df["Document"] = df["Document"].apply(lambda x: "✅ Uploaded" if x else "❌ None")
            st.dataframe(df, use_container_width=True, hide_index=True)

            # View details
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

            # Delete
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
    st.markdown("## 🪑 Asset Management")

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

            # Delete
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
    st.markdown("## 📈 Reports")

    rtype = st.selectbox("Report Type", ["Booking Report", "Revenue Report", "Expense Report"])
    c1, c2 = st.columns(2)
    dfrom = c1.date_input("From Date", value=date.today().replace(day=1))
    dto = c2.date_input("To Date", value=date.today())

    if st.button("Generate Report", type="primary"):
        fstr = dfrom.isoformat()
        tstr = dto.isoformat()

        if rtype == "Booking Report":
            try:
                data = supabase.table("bookings").select("*").gte("event_date", fstr).lte("event_date", tstr).execute().data or []
            except Exception as e:
                st.error(f"Error: {e}")
                data = []
            if data:
                df = pd.DataFrame(data)[["event_date", "event_name", "customer_name", "hall_name", "event_type", "total_amount", "status"]]
                df.columns = ["Date", "Event", "Customer", "Hall", "Type", "Amount", "Status"]
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.markdown(f"**Total Bookings:** {len(data)} | **Total Value:** {fmt_currency(sum(b.get('total_amount', 0) for b in data))}")
            else:
                st.info("No bookings in selected range")

        elif rtype == "Revenue Report":
            try:
                data = supabase.table("payments").select("*, bookings(event_name, customer_name)").gte("payment_date", fstr).lte("payment_date", tstr).execute().data or []
            except Exception as e:
                st.error(f"Error: {e}")
                data = []
            if data:
                for d in data:
                    bk = d.get("bookings", {})
                    d["event_name"] = bk.get("event_name", "")
                    d["customer_name"] = bk.get("customer_name", "")
                df = pd.DataFrame(data)[["payment_date", "customer_name", "event_name", "amount", "method"]]
                df.columns = ["Date", "Customer", "Event", "Amount", "Method"]
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.markdown(f"**Total Revenue:** {fmt_currency(df['Amount'].sum())}")
            else:
                st.info("No payments in selected range")

        elif rtype == "Expense Report":
            try:
                data = supabase.table("expenses").select("*").gte("expense_date", fstr).lte("expense_date", tstr).execute().data or []
            except Exception as e:
                st.error(f"Error: {e}")
                data = []
            if data:
                df = pd.DataFrame(data)[["expense_date", "category", "description", "amount", "paid_to"]]
                df.columns = ["Date", "Category", "Description", "Amount", "Vendor"]
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.markdown(f"**Total Expenses:** {fmt_currency(df['Amount'].sum())}")
            else:
                st.info("No expenses in selected range")

    st.markdown("---")
    if st.button("🖨️ Print Page", type="secondary"):
        st.markdown("""
        <script>window.print();</script>
        """, unsafe_allow_html=True)

# ==================== MAIN ====================
def main():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
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

if __name__ == "__main__":
    main()
