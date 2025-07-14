# --- ИЗМЕНЕНИЕ: Добавлен недостающий импорт ---
from datetime import datetime, timezone
# --- КОНЕЦ ИЗМЕНЕНИЯ ---
from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Auth(Base):
    __tablename__ = 'auth'
    auth_type = Column(Text, primary_key=True)
    username = Column(Text)
    password = Column(Text)
    url = Column(Text)

class Series(Base):
    __tablename__ = 'series'
    id = Column(Integer, primary_key=True)
    url = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    name_en = Column(Text, nullable=False)
    site = Column(Text, nullable=False)
    save_path = Column(Text, nullable=False)
    season = Column(Text, nullable=True) 
    quality = Column(Text)
    state = Column(Text, default='waiting') 
    last_scan_time = Column(DateTime)
    auto_scan_enabled = Column(Boolean, default=False, nullable=False)
    active_status = Column(Text, default='{}')
    quality_override = Column(Text, nullable=True)
    resolution_override = Column(Text, nullable=True)

class RenamingPattern(Base):
    __tablename__ = 'renaming_patterns'
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    pattern = Column(Text, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

class SeasonPattern(Base):
    __tablename__ = 'season_patterns'
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    pattern = Column(Text, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
class AdvancedRenamingPattern(Base):
    __tablename__ = 'advanced_renaming_patterns'
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    file_filter = Column(Text, nullable=False)
    pattern_search = Column(Text, nullable=False)
    area_to_replace = Column(Text, nullable=False)
    replacement_template = Column(Text, nullable=False)
    arithmetic_op = Column(Integer, nullable=True)
    priority = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

class Torrent(Base):
    __tablename__ = 'torrents'
    id = Column(Integer, primary_key=True)
    series_id = Column(Integer, ForeignKey('series.id'))
    torrent_id = Column(Text, nullable=False, unique=True)
    link = Column(Text, nullable=False)
    date_time = Column(Text)
    quality = Column(Text)
    episodes = Column(Text)
    is_active = Column(Boolean, default=True)
    qb_hash = Column(Text)
    series = relationship("Series")

class Setting(Base):
    __tablename__ = 'settings'
    key = Column(Text, primary_key=True)
    value = Column(Text)

class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    group = Column(Text, nullable=False)
    level = Column(Text, nullable=False)
    message = Column(Text, nullable=False)

class QualityPattern(Base):
    __tablename__ = 'quality_patterns'
    id = Column(Integer, primary_key=True)
    standard_value = Column(Text, nullable=False, unique=True)
    priority = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    search_patterns = relationship("QualitySearchPattern", back_populates="quality_pattern", cascade="all, delete-orphan")

class QualitySearchPattern(Base):
    __tablename__ = 'quality_search_patterns'
    id = Column(Integer, primary_key=True)
    quality_pattern_id = Column(Integer, ForeignKey('quality_patterns.id'), nullable=False)
    pattern = Column(Text, nullable=False)
    quality_pattern = relationship("QualityPattern", back_populates="search_patterns")

class ResolutionPattern(Base):
    __tablename__ = 'resolution_patterns'
    id = Column(Integer, primary_key=True)
    standard_value = Column(Text, nullable=False, unique=True)
    priority = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    search_patterns = relationship("ResolutionSearchPattern", back_populates="resolution_pattern", cascade="all, delete-orphan")

class ResolutionSearchPattern(Base):
    __tablename__ = 'resolution_search_patterns'
    id = Column(Integer, primary_key=True)
    resolution_pattern_id = Column(Integer, ForeignKey('resolution_patterns.id'), nullable=False)
    pattern = Column(Text, nullable=False)
    resolution_pattern = relationship("ResolutionPattern", back_populates="search_patterns")

class AgentTask(Base):
    __tablename__ = 'agent_tasks'
    torrent_hash = Column(Text, primary_key=True)
    series_id = Column(Integer, nullable=False)
    torrent_id = Column(Text, nullable=False)
    old_torrent_id = Column(Text)
    stage = Column(Text, nullable=False)

class ScanTask(Base):
    __tablename__ = 'scan_tasks'
    id = Column(Integer, primary_key=True)
    series_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(Text, default='processing')
    task_data = Column(Text)
    results_data = Column(Text, default='{}')