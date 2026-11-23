INSERT INTO weeks (week_id, week_number)
SELECT range, range
FROM range(1, 17)
ON CONFLICT DO NOTHING;