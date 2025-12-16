from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    ForeignKey,
    DateTime,
    func,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(150), nullable=True)
    full_name = Column(String(255))
    role = Column(String(32), nullable=False, default="user")
    status = Column(String(32), nullable=False, default="active")
    is_email_verified = Column(Boolean, default=False)
    otp_code = Column(String(60))
    otp_expiry = Column(DateTime)
    otp_attempts = Column(Integer, default=0)
    last_otp_sent_at = Column(DateTime)
    email_verified_at = Column(DateTime)
    last_login = Column(DateTime)
    last_login_ip = Column(String(45))
    login_device_info = Column(String(255))
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)
    is_admin = Column(Boolean, default=False)

    # Relationships
    threads = relationship("Thread", back_populates="user", cascade="all, delete")
    messages = relationship("Message", back_populates="user", cascade="all, delete")
    shares = relationship("Share", back_populates="user", cascade="all, delete")

    __table_args__ = (Index("idx_otp_code_expiry", "otp_code", "otp_expiry"),)


class Thread(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255))
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="threads")
    messages = relationship("Message", back_populates="thread", cascade="all, delete")
    shares = relationship("Share", back_populates="thread", cascade="all, delete")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text)
    is_bot = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    thread_id = Column(Integer, ForeignKey("threads.id"))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="messages")
    thread = relationship("Thread", back_populates="messages")


class Share(Base):
    __tablename__ = "shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(255), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    thread_id = Column(Integer, ForeignKey("threads.id"))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="shares")
    thread = relationship("Thread", back_populates="shares")
