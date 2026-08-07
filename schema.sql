CREATE TABLE tickets (
  ticket_id  SERIAL PRIMARY KEY,
  title      TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'open',
  priority   TEXT NOT NULL DEFAULT 'medium',
  created_by TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- If tickets already exists without this column (e.g. from an earlier deploy),
-- app.py runs this same statement automatically on startup:
-- ALTER TABLE tickets ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'medium';

CREATE TABLE ticket_messages (
  message_id   SERIAL PRIMARY KEY,
  ticket_id    INTEGER NOT NULL REFERENCES tickets(ticket_id),
  message_text TEXT NOT NULL,
  author       TEXT NOT NULL,
  created_at   TIMESTAMP NOT NULL DEFAULT now()
);


INSERT INTO tickets (title, status, created_by) VALUES
('Cannot log into dashboard', 'open', 'alice'),
('Export button not working', 'in_progress', 'bob'),
('Feature request: dark mode', 'resolved', 'carol');

INSERT INTO ticket_messages (ticket_id, message_text, author) VALUES
(1, 'I keep getting an invalid password error even after resetting.', 'alice'),
(1, 'Can you confirm which browser you are using?', 'support-agent'),
(2, 'Clicking export just spins forever.', 'bob'),
(2, 'We are looking into a timeout issue on large exports.', 'support-agent'),
(3, 'Would love a dark mode option.', 'carol'),
(3, 'Dark mode shipped in the latest release — please refresh!', 'support-agent');

