PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ---------- roles ----------
CREATE TABLE roles (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

-- ---------- users ----------
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL UNIQUE CHECK (email LIKE '%_@_%._%'),
    full_name   TEXT NOT NULL,
    department  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_role   INTEGER REFERENCES user_roles(id)
);

-- ---------- user_roles ----------
CREATE TABLE user_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

-- ---------- categories (self-ref) ----------
CREATE TABLE categories (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL UNIQUE,
    parent_id INTEGER REFERENCES categories(id) ON DELETE SET NULL
);

-- ---------- statuses ----------
CREATE TABLE statuses (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL UNIQUE,
    is_closed INTEGER NOT NULL DEFAULT 0 CHECK (is_closed IN (0,1))
);

-- ---------- tickets ----------
CREATE TABLE tickets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT,
    author_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assignee_id  INTEGER          REFERENCES users(id) ON DELETE SET NULL,
    category_id  INTEGER          REFERENCES categories(id) ON DELETE SET NULL,
    status_id    INTEGER NOT NULL REFERENCES statuses(id) ON DELETE RESTRICT,
    priority     TEXT NOT NULL DEFAULT 'normal'
                 CHECK (priority IN ('low','normal','high','critical')),
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at    TEXT
);

CREATE INDEX idx_tickets_author    ON tickets(author_id);
CREATE INDEX idx_tickets_assignee  ON tickets(assignee_id);
CREATE INDEX idx_tickets_status    ON tickets(status_id);
CREATE INDEX idx_tickets_category  ON tickets(category_id);
CREATE INDEX idx_tickets_created   ON tickets(created_at);

-- ---------- comments ----------
CREATE TABLE comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id  INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_internal INTEGER NOT NULL DEFAULT 0 CHECK (is_internal IN (0,1))
);

CREATE INDEX idx_comments_ticket ON comments(ticket_id);

-- ---------- attachments ----------
CREATE TABLE attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   INTEGER          REFERENCES tickets(id)  ON DELETE CASCADE,
    comment_id  INTEGER          REFERENCES comments(id) ON DELETE CASCADE,
    uploaded_by INTEGER NOT NULL REFERENCES users(id)    ON DELETE RESTRICT,
    file_name   TEXT NOT NULL,
    file_size   INTEGER NOT NULL CHECK (file_size >= 0),
    mime_type   TEXT,
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (ticket_id IS NOT NULL OR comment_id IS NOT NULL)
);

CREATE INDEX idx_attach_ticket  ON attachments(ticket_id);
CREATE INDEX idx_attach_comment ON attachments(comment_id);

-- ---------- ticket_status_history ----------
CREATE TABLE ticket_status_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id  INTEGER NOT NULL REFERENCES tickets(id)  ON DELETE CASCADE,
    status_id  INTEGER NOT NULL REFERENCES statuses(id) ON DELETE RESTRICT,
    changed_by INTEGER NOT NULL REFERENCES users(id)    ON DELETE RESTRICT,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note       TEXT
);

CREATE INDEX idx_hist_ticket ON ticket_status_history(ticket_id);

-- ---------- Триггер: обновление updated_at и closed_at ----------
CREATE TRIGGER trg_tickets_updated_at
AFTER UPDATE OF status_id ON tickets
FOR EACH ROW
BEGIN
    UPDATE tickets
       SET updated_at = CURRENT_TIMESTAMP,
           closed_at  = CASE
                            WHEN (SELECT is_closed FROM statuses WHERE id = NEW.status_id) = 1
                                 AND NEW.closed_at IS NULL THEN CURRENT_TIMESTAMP
                            WHEN (SELECT is_closed FROM statuses WHERE id = NEW.status_id) = 0
                                 THEN NULL
                            ELSE NEW.closed_at
                        END
     WHERE id = NEW.id;
END;
