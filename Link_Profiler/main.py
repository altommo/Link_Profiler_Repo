crawl_service_for_lifespan = CrawlService(
    # ...
    resilience_manager=distributed_resilience_manager # This argument is being passed
)
