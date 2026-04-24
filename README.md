# SMCCD Transfer Guide

STG is a Django planner for SMCCD transfer students. It reads imported school course data from `database.db` and stores transfer paths, student plan items, major-prep requirements, and ASSIST articulation entries in Django-managed tables in the same SQLite database.

## Run

```powershell
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Current Features

- Starter transfer paths for IGETC, CSU GE Breadth, and the UC 7-course pattern.
- Progressive requirement areas with expandable sections.
- Session-based student plan items with completion toggles.
- Course search over the imported SMCCD schedule table.
- Admin-editable major plans, major requirements, and ASSIST articulation rules.

## Admin

Create an admin user with:

```powershell
python manage.py createsuperuser
```

Then open `http://127.0.0.1:8000/admin/` to add ASSIST conversions and major-prep requirements.

## Import ASSIST Major Agreements

Import a bounded test set:

```powershell
python manage.py scrape_assist --targets "University of California, Berkeley" "University of California, Santa Cruz" --major-limit 2
```

Import all available non-community-college targets for the three SMCCD colleges:

```powershell
python manage.py scrape_assist
```

Useful limits while testing:

```powershell
python manage.py scrape_assist --target-limit 5 --major-limit 10
```

The scraper defaults to ASSIST academic year `2025-2026` (`academic_year_id=76`). Raw ASSIST JSON is kept in `assist_json/` by default. Use `--refresh-cache` to force a re-download of cached files.
