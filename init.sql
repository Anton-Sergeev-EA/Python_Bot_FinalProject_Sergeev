-- Initialize database with some default data.

-- Insert default categories.
INSERT INTO categories (name, description, is_active) VALUES
('Электроника', 'Смартфоны, ноутбуки, планшеты, фотоаппараты, игровые консоли', true),
('Транспорт', 'Велосипеды, самокаты, электросамокаты, скейтборды', true),
('Одежда', 'Одежда для мероприятий, спецодежда, костюмы', true),
('Инструменты', 'Строительные инструменты, садовый инвентарь', true),
('Спорт', 'Спортивный инвентарь, тренажеры, снаряжение', true),
('Книги', 'Книги, учебники, журналы', true),
('Мебель', 'Мебель для мероприятий, временное использование', true),
('Другое', 'Прочие товары для аренды', true)
ON CONFLICT (name) DO NOTHING;

-- Create indexes for better performance.
CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status);
CREATE INDEX IF NOT EXISTS idx_ads_owner ON ads(owner_id);
CREATE INDEX IF NOT EXISTS idx_ads_location ON ads(location);
CREATE INDEX IF NOT EXISTS idx_ads_price ON ads(price);
CREATE INDEX IF NOT EXISTS idx_ads_created ON ads(created_at);

CREATE INDEX IF NOT EXISTS idx_messages_ad ON messages(ad_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at);

CREATE INDEX IF NOT EXISTS idx_search_queries_user ON search_queries(user_id);
CREATE INDEX IF NOT EXISTS idx_search_queries_active ON search_queries(is_active);
