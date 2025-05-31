from setuptools import setup, find_packages

# Read dependencies from requirements.txt
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="Link_Profiler",
    version="0.1",
    packages=find_packages(),
    install_requires=requirements, # Use dependencies from requirements.txt
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
