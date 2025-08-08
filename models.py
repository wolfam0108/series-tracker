from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, DateTime, func, Float
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
    files = relationship("TorrentFile", back_populates="torrent", cascade="all, delete-orphan")

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
    
    source_title = Column(Text, nullable=True)

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

    total_size_mb = Column(Float, nullable=True) # Размер файла в мегабайтах

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

class TorrentFile(Base):
    __tablename__ = 'torrent_files'
    id = Column(Integer, primary_key=True)
    torrent_db_id = Column(Integer, ForeignKey('torrents.id'), nullable=False)

    original_path = Column(Text, nullable=False)
    renamed_path = Column(Text, nullable=True)
    status = Column(Text, default='pending_rename', nullable=False) # e.g., pending_rename, renamed, skipped
    extracted_metadata = Column(Text) # Stored as JSON

    torrent = relationship("Torrent", back_populates="files")

class RelocationTask(Base):
    __tablename__ = 'relocation_tasks'
    id = Column(Integer, primary_key=True)
    series_id = Column(Integer, nullable=False, index=True)
    new_path = Column(Text, nullable=False)
    status = Column(Text, default='pending', nullable=False) # pending, in_progress, completed, error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class RenamingTask(Base):
    __tablename__ = 'renaming_tasks'
    id = Column(Integer, primary_key=True)

    series_id = Column(Integer, nullable=False, index=True)
    
    media_item_unique_id = Column(Text, nullable=True, index=True)
    old_path = Column(Text, nullable=True)
    new_path = Column(Text, nullable=True)

    status = Column(Text, default='pending', nullable=False)
    attempts = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    task_type = Column(Text, default='single_vk', nullable=False) # e.g., 'single_vk', 'mass_torrent_reprocess'
    task_data = Column(Text, nullable=True) # Для будущих задач, пока не используется

class Tracker(Base):
    __tablename__ = 'trackers'
    id = Column(Integer, primary_key=True)
    canonical_name = Column(Text, nullable=False, unique=True) # Системное имя, например, 'anilibria'
    display_name = Column(Text, nullable=False) # Имя для UI, например, 'Anilibria'
    mirrors = Column(Text, default='[]') # JSON-список зеркал
    parser_class = Column(Text, nullable=False) # Имя класса-парсера
    auth_type = Column(Text, default='none', nullable=False)
    ui_features = Column(Text, default='{}') # JSON-объект с флагами для UI