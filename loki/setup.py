from setuptools import setup, find_packages

setup(
    name="loki",
    version="1.0.0",
    description="GitHub Social Engineering Honeypot & Threat Intelligence",
    packages=find_packages(),
    install_requires=[
        "typer[all]>=0.9.0",
        "rich>=13.7.0",
        "requests>=2.31.0",
        "PyGitHub>=2.1.1",
        "dulwich>=0.21.7",
    ],
    entry_points={
        "console_scripts": [
            "loki=loki.cli.main:app",
        ],
    },
    python_requires=">=3.9",
)
