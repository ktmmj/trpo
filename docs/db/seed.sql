-- ============================================================
-- Тестовые данные для схемы
-- ============================================================
PRAGMA foreign_keys = ON;

-- ---------- user_roles ----------
INSERT INTO user_roles (name) VALUES
    ('admin'),
    ('agent'),
    ('employee');

-- ---------- roles (альтернативная таблица ролей) ----------
INSERT INTO roles (name, description) VALUES
    ('administrator', 'Полный доступ к системе'),
    ('support_agent', 'Обработка заявок'),
    ('employee',      'Сотрудник, подающий заявки');

-- ---------- users ----------
INSERT INTO users (email, full_name, department, is_active, user_role) VALUES
    ('ivanov@company.ru',   'Иван Иванов',    'IT',            1, 1),
    ('petrova@company.ru',  'Мария Петрова',  'HR',            1, 2),
    ('sidorov@company.ru',  'Алексей Сидоров','Finance',       1, 3),
    ('kuznetsova@company.ru','Ольга Кузнецова','IT',           1, 2),
    ('smirnov@company.ru',  'Дмитрий Смирнов','Sales',         1, 3),
    ('volkova@company.ru',  'Анна Волкова',   'Marketing',     0, 3);

-- ---------- categories (иерархия) ----------
INSERT INTO categories (name, parent_id) VALUES
    ('Оборудование',        NULL),  -- 1
    ('Программное обеспечение', NULL), -- 2
    ('Доступы',             NULL),  -- 3
    ('Компьютеры',          1),     -- 4
    ('Периферия',           1),     -- 5
    ('ОС и драйверы',       2),     -- 6
    ('Учётные записи',      3);     -- 7

-- ---------- statuses ----------
INSERT INTO statuses (name, is_closed) VALUES
    ('open',       0),
    ('in_progress',0),
    ('pending',    0),
    ('resolved',   1),
    ('closed',     1);

-- ---------- tickets ----------
INSERT INTO tickets (title, description, author_id, assignee_id, category_id, status_id, priority) VALUES
    ('Не включается ноутбук',                'После обновления ОС ноутбук перестал загружаться.',        3, 2, 4, 1, 'high'),
    ('Не работает принтер в 315 кабинете',   'Ошибка "offline" при печати.',                             5, 4, 5, 2, 'normal'),
    ('Требуется доступ к 1С',                'Нужен доступ для нового сотрудника в отдел продаж.',        3, 2, 7, 1, 'normal'),
    ('Ошибка Outlook при запуске',           'Приложение падает при старте с кодом 0x80040600.',          1, 4, 6, 3, 'high'),
    ('Замена картриджа',                     'Закончился тонер в МФУ на 2 этаже.',                        5, NULL, 5, 1, 'low'),
    ('Установить Photoshop',                 'Требуется для работы над рекламными материалами.',          6, NULL, 2, 1, 'critical'),
    ('Медленно работает компьютер',          'Загрузка занимает более 10 минут.',                        1, 4, 4, 4, 'normal');

-- ---------- comments ----------
INSERT INTO comments (ticket_id, author_id, body, is_internal) VALUES
    (1, 2, 'Здравствуйте! Уточните модель ноутбука.', 0),
    (1, 3, 'Dell XPS 15, инвентарный номер IT-1023.', 0),
    (1, 2, 'Попробуйте загрузиться в безопасном режиме.', 0),
    (1, 4, 'Похоже на проблему с драйвером видеокарты. Проверю удалённо.', 1),
    (2, 4, 'Перезагрузил принтер, статус изменился на "ready".', 0),
    (3, 2, 'Доступ выдан, проверьте пожалуйста.', 0),
    (4, 4, 'Требуется переустановка профиля Outlook.', 1),
    (7, 4, 'Рекомендую заменить HDD на SSD. Согласуйте с руководителем.', 0);

-- ---------- attachments ----------
INSERT INTO attachments (ticket_id, comment_id, uploaded_by, file_name, file_size, mime_type) VALUES
    (1, NULL, 3, 'screenshot_error.png', 245760, 'image/png'),
    (1, 2,    3, 'dxdiag_report.txt',    15360,  'text/plain'),
    (2, NULL, 5, 'printer_photo.jpg',    512000, 'image/jpeg'),
    (4, 7,    1, 'outlook_crash.log',    32768,  'text/plain'),
    (NULL, 4, 4, 'driver_notes.pdf',     102400, 'application/pdf');

-- ---------- ticket_status_history ----------
INSERT INTO ticket_status_history (ticket_id, status_id, changed_by, note) VALUES
    (1, 1, 3, 'Заявка создана'),
    (1, 2, 2, 'Взята в работу'),
    (2, 1, 5, 'Заявка создана'),
    (2, 2, 4, 'Взята в работу'),
    (2, 3, 4, 'Ожидание ответа пользователя'),
    (3, 1, 3, 'Заявка создана'),
    (4, 1, 1, 'Заявка создана'),
    (4, 2, 4, 'Взята в работу'),
    (4, 3, 4, 'Ожидание переустановки профиля'),
    (7, 1, 1, 'Заявка создана'),
    (7, 2, 4, 'Взята в работу'),
    (7, 4, 4, 'Проблема решена, рекомендована замена HDD');
