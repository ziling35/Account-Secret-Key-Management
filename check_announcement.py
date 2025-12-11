from app.database import SessionLocal
from app.models import Announcement

db = SessionLocal()
announcements = db.query(Announcement).all()
print(f'公告数量: {len(announcements)}')
for a in announcements:
    print(f'ID: {a.id}')
    print(f'Active: {a.is_active}')
    print(f'Content: {a.content[:100]}...')
    print('---')
db.close()
