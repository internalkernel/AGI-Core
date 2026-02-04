from setuptools import setup, find_packages

setup(
    name="openclaw-memory-system",
    version="1.0.0",
    description="Tiered memory architecture for OpenClaw agents",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="OpenClaw Community",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "memory_system": ["templates/*", "utils/*"],
    },
    install_requires=[
        "numpy>=1.20.0",
        "requests>=2.25.0",
    ],
    extras_require={
        "dev": ["pytest", "black", "mypy"],
    },
    entry_points={
        "console_scripts": [
            "memory=utils.memory_cli:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: JavaScript",
    ],
)
