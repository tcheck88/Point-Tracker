# models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "Users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    nickname = Column(String(100))
    phone = Column(String(50))
    email = Column(String(254))
    parent_name = Column(String(200))
    sms_consent = Column(Boolean, nullable=False, default=False)
    classroom = Column(String(100))
    grade = Column(String(50))
    total_points = Column(Integer, nullable=False, default=0)
    referral_code = Column(String(100))
    created_by = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    modified_by = Column(String(100))
    modified_at = Column(DateTime)
    merge_into = Column(Integer)
    merge_justification = Column(Text)
    active = Column(Boolean, nullable=False, default=True)

class Transaction(Base):
    __tablename__ = "Transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    date = Column(DateTime, server_default=func.now())
    activity = Column(Text)
    points = Column(Integer)
    performed_by = Column(String(100))

class AuditLog(Base):
    __tablename__ = "Audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_time = Column(DateTime, server_default=func.now())
    event_type = Column(String(100), nullable=False)
    actor = Column(String(100))
    target_table = Column(String(100))
    target_id = Column(Integer)
    details = Column(Text)

class DuplicateLog(Base):
    __tablename__ = "Duplicate_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_time = Column(DateTime, server_default=func.now())
    checked_name = Column(String(200))
    checked_phone = Column(String(50))
    checked_email = Column(String(254))
    matches = Column(Text)
    actor = Column(String(100))
    action_taken = Column(String(100))
    justification = Column(Text)