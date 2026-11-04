
INSERT INTO mart.sectors (sector_name)
VALUES
    ('Communication Services'),
    ('Consumer Discretionary'),
    ('Consumer Staples'),
    ('Energy'),
    ('Financials'),
    ('Health Care'),
    ('Industrials'),
    ('Information Technology'),
    ('Materials'),
    ('Real Estate'),
    ('Utilities')
ON CONFLICT (sector_name) DO NOTHING;
