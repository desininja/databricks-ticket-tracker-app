import streamlit as st
import psycopg2
import os

st.set_page_config(page_title="Support Ticket System", page_icon="🎫", layout="wide")

STATUSES = ["open", "in_progress", "resolved"]
PRIORITIES = ["low", "medium", "high"]
STATUS_BADGE = {"open": "🟡 Open", "in_progress": "🔵 In Progress", "resolved": "🟢 Resolved"}
PRIORITY_BADGE = {"low": "⬇️ Low", "medium": "➡️ Medium", "high": "🔺 High"}


def get_connection():
    """Connect to Lakebase using environment variables provided by app.yaml."""
    return psycopg2.connect(
        host=os.environ["LAKEBASE_HOST"],
        port=os.environ.get("LAKEBASE_PORT", "5432"),
        dbname=os.environ["LAKEBASE_DB"],
        user=os.environ["LAKEBASE_USER"],
        password=os.environ["LAKEBASE_PASSWORD"],
        sslmode="require",
    )


def ensure_schema(conn):
    """Best-effort, idempotent migration so existing deployments pick up the
    priority column. The app connects with a least-privilege role that may not
    own the table (and therefore can't run ALTER TABLE) — if so, this is a
    no-op and the column must be added once by the table owner instead
    (see schema.sql)."""
    try:
        with conn.cursor() as migrate_cur:
            migrate_cur.execute(
                "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'medium'"
            )
        conn.commit()
    except Exception:
        conn.rollback()


def flash(kind, message):
    st.session_state.flash = (kind, message)


conn = get_connection()
ensure_schema(conn)
cur = conn.cursor()

if "confirm_delete_id" not in st.session_state:
    st.session_state.confirm_delete_id = None
if "flash" not in st.session_state:
    st.session_state.flash = None

st.title("🎫 Support Ticket System")

if st.session_state.flash:
    kind, message = st.session_state.flash
    getattr(st, kind)(message)
    st.session_state.flash = None

# ---------------- Stats ----------------
cur.execute("SELECT status, COUNT(*) FROM tickets GROUP BY status")
status_counts = dict(cur.fetchall())
cur.execute("SELECT COUNT(*) FROM ticket_messages")
total_messages = cur.fetchone()[0]
total_tickets = sum(status_counts.values())

stat_cols = st.columns(5)
stat_cols[0].metric("Total tickets", total_tickets)
stat_cols[1].metric("🟡 Open", status_counts.get("open", 0))
stat_cols[2].metric("🔵 In progress", status_counts.get("in_progress", 0))
stat_cols[3].metric("🟢 Resolved", status_counts.get("resolved", 0))
stat_cols[4].metric("💬 Messages", total_messages)

st.divider()

# ---------------- Sidebar: create ticket + filter ----------------
with st.sidebar:
    st.header("➕ New ticket")
    with st.form("create_ticket_form", clear_on_submit=True):
        title = st.text_input("Title")
        creator = st.text_input("Created by")
        priority = st.selectbox("Priority", PRIORITIES, index=1)
        submitted = st.form_submit_button("Create ticket", type="primary")

    if submitted:
        title_clean = (title or "").strip()
        creator_clean = (creator or "").strip()
        errors = []
        if not title_clean:
            errors.append("Title is required.")
        elif len(title_clean) < 3:
            errors.append("Title must be at least 3 characters.")
        elif len(title_clean) > 200:
            errors.append("Title must be under 200 characters.")
        if not creator_clean:
            errors.append("Created by is required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            cur.execute("SELECT 1 FROM tickets WHERE LOWER(title) = LOWER(%s)", (title_clean,))
            is_duplicate = cur.fetchone() is not None
            cur.execute(
                "INSERT INTO tickets (title, status, created_by, priority) VALUES (%s, 'open', %s, %s)",
                (title_clean, creator_clean, priority),
            )
            conn.commit()
            note = " (a ticket with this title already existed)" if is_duplicate else ""
            flash("success", f"Ticket '{title_clean}' created{note}.")
            st.rerun()

    st.divider()
    st.caption("Filter tickets")
    status_filter = st.selectbox("Status", ["All"] + STATUSES, key="status_filter")

# ---------------- Ticket list ----------------
st.subheader("📋 Tickets")

query = "SELECT ticket_id, title, status, priority, created_by, created_at FROM tickets"
params = ()
if status_filter != "All":
    query += " WHERE status = %s"
    params = (status_filter,)
query += " ORDER BY created_at DESC"
cur.execute(query, params)
tickets = cur.fetchall()

if not tickets:
    st.info("No tickets match this filter yet.")
else:
    st.dataframe(
        [
            {
                "ID": t[0],
                "Title": t[1],
                "Status": STATUS_BADGE.get(t[2], t[2]),
                "Priority": PRIORITY_BADGE.get(t[3], t[3]),
                "Created by": t[4],
                "Created at": t[5],
            }
            for t in tickets
        ],
        hide_index=True,
        use_container_width=True,
    )

st.divider()

# ---------------- Ticket detail ----------------
if tickets:
    st.subheader("🔍 Ticket detail")
    ticket_ids = [t[0] for t in tickets]
    ticket_id = st.selectbox(
        "Select a ticket",
        ticket_ids,
        format_func=lambda tid: next(f"#{t[0]} — {t[1]}" for t in tickets if t[0] == tid),
    )
    selected = next(t for t in tickets if t[0] == ticket_id)
    _, sel_title, sel_status, sel_priority, sel_creator, sel_created = selected

    info_cols = st.columns(4)
    info_cols[0].markdown(f"**Status**  \n{STATUS_BADGE.get(sel_status, sel_status)}")
    info_cols[1].markdown(f"**Priority**  \n{PRIORITY_BADGE.get(sel_priority, sel_priority)}")
    info_cols[2].markdown(f"**Created by**  \n{sel_creator}")
    info_cols[3].markdown(f"**Created at**  \n{sel_created}")

    st.markdown("#### Messages")
    cur.execute(
        "SELECT author, message_text, created_at FROM ticket_messages WHERE ticket_id = %s ORDER BY created_at",
        (ticket_id,),
    )
    messages = cur.fetchall()
    if not messages:
        st.caption("No messages yet.")
    else:
        for author, text, created in messages:
            role = "assistant" if author == "support-agent" else "user"
            with st.chat_message(role):
                st.markdown(f"**{author}**")
                st.write(text)
                st.caption(str(created))

    with st.form("add_message_form", clear_on_submit=True):
        msg_cols = st.columns([2, 1])
        new_msg = msg_cols[0].text_input("New message")
        author = msg_cols[1].text_input("Your name")
        msg_submitted = st.form_submit_button("Add message")

    if msg_submitted:
        msg_clean = (new_msg or "").strip()
        author_clean = (author or "").strip()
        errs = []
        if not msg_clean:
            errs.append("Message text cannot be empty.")
        elif len(msg_clean) > 2000:
            errs.append("Message is too long (max 2000 characters).")
        if not author_clean:
            errs.append("Your name is required.")
        if errs:
            for e in errs:
                st.error(e)
        else:
            cur.execute(
                "INSERT INTO ticket_messages (ticket_id, message_text, author) VALUES (%s, %s, %s)",
                (ticket_id, msg_clean, author_clean),
            )
            conn.commit()
            flash("success", "Message added.")
            st.rerun()

    st.markdown("#### Update status")
    status_cols = st.columns([2, 1])
    new_status = status_cols[0].selectbox(
        "New status", STATUSES, index=STATUSES.index(sel_status), key="status_update"
    )
    if status_cols[1].button("Update status"):
        if new_status == sel_status:
            st.info("Ticket is already in that status.")
        else:
            cur.execute("UPDATE tickets SET status = %s WHERE ticket_id = %s", (new_status, ticket_id))
            conn.commit()
            flash("success", f"Ticket #{ticket_id} marked as {new_status}.")
            st.rerun()

    st.markdown("#### Danger zone")
    if st.session_state.confirm_delete_id != ticket_id:
        if st.button("🗑️ Delete this ticket"):
            st.session_state.confirm_delete_id = ticket_id
            st.rerun()
    else:
        st.warning(
            f"Permanently delete ticket #{ticket_id} and all {len(messages)} of its messages? "
            "This cannot be undone."
        )
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("✅ Yes, delete permanently", type="primary"):
            cur.execute("DELETE FROM ticket_messages WHERE ticket_id = %s", (ticket_id,))
            cur.execute("DELETE FROM tickets WHERE ticket_id = %s", (ticket_id,))
            conn.commit()
            st.session_state.confirm_delete_id = None
            flash("success", f"Ticket #{ticket_id} deleted.")
            st.rerun()
        if confirm_cols[1].button("Cancel"):
            st.session_state.confirm_delete_id = None
            st.rerun()
