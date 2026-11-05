# Архитектура

## Описание слоёв

| Компонент | Ответственность | Не должен делать |
|---|---|---|
| Controller | Принимает запрос и передаёт его дальше | Не должен содержать SQL |
| Service | Реализует бизнес-правила | Не должен рисовать интерфейс |
| Repository | Читает/изменяет данные | Не должен принимать бизнес-решения |
| Database | Хранит данные | Не должен содержать UI-логику |


## Структура

```
src
├── Controllers
│   ├── Auth
│   ├── Comment
│   └── Ticket
├── Database
│   └── Entities
│       ├── Comment
│       ├── History
│       ├── Session
│       ├── Status
│       ├── Ticket
│       └── User
├── Repository
│   ├── Impl
│   │   ├── OrmComment
│   │   ├── OrmHistory
│   │   ├── OrmSession
│   │   ├── OrmStatus
│   │   ├── OrmTicket
│   │   └── OrmUser
│   └── Interfaces
│       ├── IComment
│       ├── IHistory
│       ├── ISession
│       ├── IStatus
│       ├── ITicket
│       └── IUser
└── Service
    ├── Auth
    ├── Comment
    ├── Ticket
    └── User
```
