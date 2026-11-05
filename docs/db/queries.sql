-- Полная карточка заявки со всеми связанными данными

SELECT
    t.id,
    t.title,
    t.priority,
    s.name            AS status,
    c.name            AS category,
    a.full_name       AS author,
    asg.full_name     AS assignee,
    (SELECT COUNT(*) FROM comments    cm WHERE cm.ticket_id = t.id) AS comments_cnt,
    (SELECT COUNT(*) FROM attachments at WHERE at.ticket_id = t.id) AS attachments_cnt
FROM tickets t
JOIN statuses s   ON s.id = t.status_id
LEFT JOIN categories c ON c.id = t.category_id
JOIN users a      ON a.id = t.author_id
LEFT JOIN users asg ON asg.id = t.assignee_id
ORDER BY t.created_at DESC;

-- Вывод:
-- 7	Медленно работает компьютер	normal	resolved	Компьютеры	Иван Иванов	Ольга Кузнецова	1	0
-- 6	Установить Photoshop	critical	open	Программное обеспечение	Анна Волкова		0	0
-- 5	Замена картриджа	low	open	Периферия	Дмитрий Смирнов		0	0
-- 4	Ошибка Outlook при запуске	high	pending	ОС и драйверы	Иван Иванов	Ольга Кузнецова	1	1
-- 3	Требуется доступ к 1С	normal	open	Учётные записи	Алексей Сидоров	Мария Петрова	1	0
-- 2	Не работает принтер в 315 кабинете	normal	in_progress	Периферия	Дмитрий Смирнов	Ольга Кузнецова	1	1
-- 1	Не включается ноутбук	high	open	Компьютеры	Алексей Сидоров	Мария Петрова	4	2



-- Заявки с последним комментарием и его автором (коррелированный подзапрос + JOIN)

SELECT
    t.id,
    t.title,
    cm.body          AS last_comment,
    u.full_name      AS last_comment_author,
    cm.created_at    AS last_comment_at
FROM tickets t
LEFT JOIN comments cm
       ON cm.id = (
            SELECT id FROM comments
             WHERE ticket_id = t.id
             ORDER BY created_at DESC
             LIMIT 1
       )
LEFT JOIN users u ON u.id = cm.author_id
ORDER BY t.id;

-- Вывод:
-- 1	Не включается ноутбук	Здравствуйте! Уточните модель ноутбука.	Мария Петрова	2026-11-05 17:48:08
-- 2	Не работает принтер в 315 кабинете	Перезагрузил принтер, статус изменился на "ready".	Ольга Кузнецова	2026-11-05 17:48:08
-- 3	Требуется доступ к 1С	Доступ выдан, проверьте пожалуйста.	Мария Петрова	2026-11-05 17:48:08
-- 4	Ошибка Outlook при запуске	Требуется переустановка профиля Outlook.	Ольга Кузнецова	2026-11-05 17:48:08
-- 5	Замена картриджа
-- 6	Установить Photoshop
-- 7	Медленно работает компьютер	Рекомендую заменить HDD на SSD. Согласуйте с руководителем.	Ольга Кузнецова	2026-11-05 17:48:08



-- Полная история смены статусов с временем пребывания в каждом статусе (оконные функции)

SELECT
    t.id AS ticket_id,
    t.title,
    sh.changed_at,
    st.name                AS status,
    u.full_name            AS changed_by,
    LEAD(sh.changed_at) OVER (PARTITION BY sh.ticket_id ORDER BY sh.changed_at) AS next_change,
    ROUND(
        julianday(LEAD(sh.changed_at) OVER (PARTITION BY sh.ticket_id ORDER BY sh.changed_at))
        - julianday(sh.changed_at), 2
    ) AS hours_in_status
FROM ticket_status_history sh
JOIN tickets  t ON t.id = sh.ticket_id
JOIN statuses st ON st.id = sh.status_id
JOIN users    u ON u.id = sh.changed_by
ORDER BY sh.ticket_id, sh.changed_at;



Вывод:
-- 1	Не включается ноутбук	2026-11-05 17:48:08	open	Алексей Сидоров	2026-11-05 17:48:08	0.0
-- 1	Не включается ноутбук	2026-11-05 17:48:08	in_progress	Мария Петрова
-- 2	Не работает принтер в 315 кабинете	2026-11-05 17:48:08	open	Дмитрий Смирнов	2026-11-05 17:48:08	0.0
-- 2	Не работает принтер в 315 кабинете	2026-11-05 17:48:08	in_progress	Ольга Кузнецова	2026-11-05 17:48:08	0.0
-- 2	Не работает принтер в 315 кабинете	2026-11-05 17:48:08	pending	Ольга Кузнецова
-- 3	Требуется доступ к 1С	2026-11-05 17:48:08	open	Алексей Сидоров
-- 4	Ошибка Outlook при запуске	2026-11-05 17:48:08	open	Иван Иванов	2026-11-05 17:48:08	0.0
-- 4	Ошибка Outlook при запуске	2026-11-05 17:48:08	in_progress	Ольга Кузнецова	2026-11-05 17:48:08	0.0
-- 4	Ошибка Outlook при запуске	2026-11-05 17:48:08	pending	Ольга Кузнецова
-- 7	Медленно работает компьютер	2026-11-05 17:48:08	open	Иван Иванов	2026-11-05 17:48:08	0.0
-- 7	Медленно работает компьютер	2026-11-05 17:48:08	in_progress	Ольга Кузнецова	2026-11-05 17:48:08	0.0
-- 7	Медленно работает компьютер	2026-11-05 17:48:08	resolved	Ольга Кузнецова
