import streamlit as st
import psycopg2
import os

def get_connection():
    """
    Connect to Lakebase using environment variables provided by app.yaml.
    """
    return psycopg2.connect(
        host=os.environ["LAKEBASE_HOST"],
        port=os.environ.get("LAKEBASE_PORT", "5432"),
        dbname=os.environ["LAKEBASE_DB"],
        user=os.environ["LAKEBASE_USER"],
        password=os.environ["LAKEBASE_PASSWORD"],
        sslmode="require",
    )

st.title("Support Ticket System")

conn = get_connection()
cur = conn.cursor()

# View all tickets
cur.execute("SELECT ticket_id, title, status, created_by, craeted_at FROM tickets ORDER BY craeted_at DESC")
tickets = cur.fetchall()

for t in tickets:
    st.write(f"#{t[0]} — {t[1]} [{t[2]}] by {t[3]}")

# Select a ticket to view messages
ticket_id = st.selectbox("Select ticket", [t[0] for t in tickets])
cur.execute("SELECT author, message_text, craeted_at FROM ticket_messages WHERE ticket_id=%s ORDER BY craeted_at", (ticket_id,))
for m in cur.fetchall():
    st.write(f"**{m[0]}**: {m[1]} ({m[2]})")

# Add a message
new_msg = st.text_input("New message")
author = st.text_input("Your name")
if st.button("Add message") and new_msg and author:
    cur.execute(
        "INSERT INTO ticket_messages (ticket_id, message_text, author) VALUES (%s, %s, %s)",
        (ticket_id, new_msg, author),
    )
    conn.commit()
    st.rerun()

# Update status
new_status = st.selectbox("Update status", ["open", "in_progress", "resolved"])
if st.button("Update status"):
    cur.execute("UPDATE tickets SET status=%s WHERE ticket_id=%s", (new_status, ticket_id))
    conn.commit()
    st.rerun()

# Create new ticket
st.subheader("Create new ticket")
title = st.text_input("Title")
creator = st.text_input("Created by")
if st.button("Create ticket") and title and creator:
    cur.execute(
        "INSERT INTO tickets (title, status, created_by) VALUES (%s, 'open', %s)",
        (title, creator),
    )
    conn.commit()
    st.rerun()