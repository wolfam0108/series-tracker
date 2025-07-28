from datetime import datetime, timezone
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
    # Поле state остается для хранения простого агрегированного статуса для UI
    state = Column(Text, default='waiting') 
    last_scan_time = Column(DateTime)
    auto_scan_enabled = Column(Boolean, default=False, nullable=False)
    quality_override = Column(Text, nullable=True)
    resolution_override = Column(Text, nullable=True)
    source_type = Column(Text, default='torrent', nullable=False)
    parser_profile_id = Column(Integer, ForeignKey('parser_profiles.id'), nullable=True)
    ignored_seasons = Column(Text, default='[]')
    vk_search_mode = Column(Text, default='search', nullable=False)
    vk_quality_priority = Column(Text, nullable=True)
    
    statuses = relationship("SeriesStatus", back_populates="series", uselist=False, cascade="all, delete-orphan")

class SeriesStatus(Base):
    __tablename__ = 'series_statuses'
    series_id = Column(Integer, ForeignKey('series.id'), primary_key=True)
    
    is_waiting = Column(Boolean, default=True, nullable=False)
    is_scanning = Column(Boolean, default=False, nullable=False)
    is_metadata = Column(Boolean, default=False, nullable=False)
    is_renaming = Column(Boolean, default=False, nullable=False)
    is_checking = Column(Boolean, default=False, nullable=False)
    is_activating = Column(Boolean, default=False, nullable=False)
    is_downloading = Column(Boolean, default=False, nullable=False)
    is_slicing = Column(Boolean, default=False, nullable=False)
    is_ready = Column(Boolean, default=False, nullable=False)
    is_error = Column(Boolean, default=False, nullable=False)
    is_viewing = Column(DateTime, nullable=True) 
    
    series = relationship("Series", back_populates="statuses")

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

class ParserProfile(Base):
    __tablename__ = 'parser_profiles'
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    preferred_voiceovers = Column(Text)
    rules = relationship("ParserRule", back_populates="profile", cascade="all, delete-orphan", order_by="ParserRule.priority")

class ParserRule(Base):
    __tablename__ = 'parser_rules'
    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('parser_profiles.id'), nullable=False)
    name = Column(Text, nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    action_pattern = Column(Text)
    continue_after_match = Column(Boolean, default=False, nullable=False)
    profile = relationship("ParserProfile", back_populates="rules")
    conditions = relationship("ParserRuleCondition", back_populates="rule", cascade="all, delete-orphan", order_by="ParserRuleCondition.id")

class ParserRuleCondition(Base):
    __tablename__ = 'parser_rule_conditions'
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('parser_rules.id'), nullable=False)
    condition_type = Column(Text, nullable=False)
    pattern = Column(Text, nullable=False)
    logical_operator = Column(Text, default='AND', nullable=False)
    rule = relationship("ParserRule", back_populates="conditions")

class MediaItem(Base):
    __tablename__ = 'media_items'
    id = Column(Integer, primary_key=True)
    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)
    unique_id = Column(Text, nullable=False, unique=True) 
    
    season = Column(Integer, nullable=True)
    episode_start = Column(Integer, nullable=False)
    episode_end = Column(Integer, nullable=True) 
    
    plan_status = Column(Text, default='candidate', nullable=False) # Статус от SmartCollector
    status = Column(Text, default='pending', nullable=False) # Статус выполнения от Агентов
    is_ignored_by_user = Column(Boolean, default=False, nullable=False)

    source_url = Column(Text, nullable=False)
    publication_date = Column(DateTime, nullable=False)
    voiceover_tag = Column(Text)
    
    final_filename = Column(Text, nullable=True)
    
    chapters = Column(Text, nullable=True) # Поле для хранения глав в формате JSON
    slicing_status = Column(Text, default='none', nullable=False) # none, pending, slicing, completed, error
    is_available = Column(Boolean, default=True, nullable=False)

    resolution = Column(Integer, nullable=True) # Максимальное разрешение видео, e.g., 1080

    series = relationship("Series")

class DownloadTask(Base):
    __tablename__ = 'download_tasks'
    id = Column(Integer, primary_key=True)
    task_key = Column(Text, nullable=False, index=True) # Хранит unique_id для VK или хеш для торрента
    series_id = Column(Integer, nullable=False)
    
    # Поля для VK-задач
    video_url = Column(Text, nullable=True)
    save_path = Column(Text, nullable=True)
    
    status = Column(Text, default='pending', nullable=False) # pending, downloading, completed, error | qBit-статус для торрента
    error_message = Column(Text)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Новые универсальные поля
    task_type = Column(Text, default='vk_video', nullable=False) # 'vk_video' или 'torrent'
    progress = Column(Integer, default=0)  # Хранит прогресс в процентах (0-100)
    dlspeed = Column(Integer, default=0)   # Скорость загрузки в байтах/с
    eta = Column(Integer, default=0)       # Оставшееся время в секундах

class SlicingTask(Base):
    __tablename__ = 'slicing_tasks'
    id = Column(Integer, primary_key=True)
    media_item_unique_id = Column(Text, nullable=False, index=True)
    series_id = Column(Integer, nullable=False)
    status = Column(Text, default='pending', nullable=False)
    progress_chapters = Column(Text, default='{}')
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SlicedFile(Base):
    __tablename__ = 'sliced_files'
    id = Column(Integer, primary_key=True)
    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)
    source_media_item_unique_id = Column(Text, nullable=False, index=True)
    episode_number = Column(Integer, nullable=False)
    file_path = Column(Text, nullable=False)
    status = Column(Text, default='completed', nullable=False) # completed | missing
    series = relationship("Series")