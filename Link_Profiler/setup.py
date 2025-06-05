from setuptools import setup, find_packages

setup(
    name="Link_Profiler",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn[standard]",
        "aiohttp",
        "beautifulsoup4",
        "lxml",
        "SQLAlchemy",
        "psycopg2-binary",
        "google-api-python-client",
        "google-auth-oauthlib",
        # NEW: Added dependencies for crawler improvements
        "numpy>=1.21.0",      # Required for ML rate limiter
        "psutil>=5.8.0",      # Required for resource monitoring  
        "redis>=4.0.0",       # Required for smart queue system
        "playwright>=1.40.0", # Required for browser crawling
    ],
    # Add other metadata as needed
    author="Your Name",
    author_email="your.email@example.com",
    description="A link profiler system for expired domain recovery.",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url="https://github.com/yourusername/Link_Profiler", # Replace with your repo URL
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
