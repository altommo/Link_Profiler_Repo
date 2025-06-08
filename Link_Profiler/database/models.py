class AlertRuleORM(Base):
    __tablename__ = 'alert_rules'
    id = Column(String, primary_key=True) # UUID string
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    trigger_type = Column(String, nullable=False) # e.g., "job_status_change", "metric_threshold", "anomaly_detected"
    job_type_filter = Column(String, nullable=True) # e.g., "backlink_discovery"
    target_url_pattern = Column(String, nullable=True) # Regex pattern for target URLs

    metric_name = Column(String, nullable=True) # e.g., "seo_score", "broken_links_count"
    threshold_value = Column(Float, nullable=True)
    comparison_operator = Column(String, nullable=True) # e.g., ">", "<", ">=", "<=", "=="

    anomaly_type_filter = Column(String, nullable=True) # e.g., "captcha_spike", "crawl_rate_drop"

    severity = Column(String, default=AlertSeverityEnum.WARNING.value)
    notification_channels = Column(ARRAY(String), default=[AlertChannelEnum.DASHBOARD.value])
    notification_recipients = Column(ARRAY(String), default=[])

    created_at = Column(DateTime, default=datetime.now)
    last_triggered_at = Column(DateTime, nullable=True)
    last_fetched_at = Column(DateTime, default=datetime.utcnow) # This line is present and correct
